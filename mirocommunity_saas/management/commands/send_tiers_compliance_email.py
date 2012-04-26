# Miro Community - Easiest way to make a video website
#
# Copyright (C) 2011, 2012 Participatory Culture Foundation
# 
# Miro Community is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
# 
# Miro Community is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with Miro Community.  If not, see <http://www.gnu.org/licenses/>.

from django.core.management.base import BaseCommand

from mirocommunity_saas import models, tiers
import uploadtemplate.models

class Command(BaseCommand):

    def handle(self, *args, **options):
        ti = models.TierInfo.objects.get_current()
        if ti.already_sent_tiers_compliance_email:
            return

        warnings = tiers.user_warnings_for_downgrade(ti.tier_name)
        ### Hack
        ### Override the customtheme warning for this email with custom code
        if 'customtheme' in warnings:
            warnings.remove('customtheme')
        default_non_bundled_themes = uploadtemplate.models.Theme.objects.filter(default=True, bundled=False)
        if default_non_bundled_themes:
            warnings.add('customtheme')

        tier = ti.get_tier()
        ### Hack
        ### override the customdomain warning, too
        if (ti.site_settings.site.domain
            and not ti.site_settings.site.domain.endswith('mirocommunity.org')
            and not tier.permits_custom_domain()):
            warnings.add('customdomain')

        data = {'warnings': warnings}
        data['would_lose_admin_usernames'] = tiers.push_number_of_admins_down(
            tier.admins_limit())
        data['videos_over_limit'] = tiers.hide_videos_above_limit(tier)
        data['video_count'] = tiers.current_videos_that_count_toward_limit().count()
        tiers.send_tiers_related_multipart_email(
            'Changes to your Miro Community site',
            'mirocommunity_saas/tiers_emails/too_big_for_your_tier.txt',
            ti,
            extra_context=data)
        ti.already_sent_tiers_compliance_email = True
        ti.save()
