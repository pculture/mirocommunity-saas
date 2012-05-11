# Miro Community - Easiest way to make a video website
#
# Copyright (C) 2010, 2011, 2012 Participatory Culture Foundation
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

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.forms.models import modelformset_factory
from django.template.defaultfilters import pluralize

from mirocommunity_saas.models import Tier

from localtv.models import Video

from localtv.admin.forms import (EditSettingsForm as _EditSettingsForm,
                                 AuthorForm as _AuthorForm,
                                 BulkEditVideoFormSet as _BulkEditVideoFormSet,
                                 BulkEditVideoForm)

class EditSettingsForm(_EditSettingsForm):
    def __init__(self, *args, **kwargs):
        _EditSettingsForm.__init__(self, *args, **kwargs)
        self.tier = Tier.objects.get(sitetierinfo__site=settings.SITE_ID)
        if not self.tier.custom_css:
            # Uh-oh: custom CSS is not permitted!
            #
            # To handle only letting certain paid users edit CSS,
            # we do two things.
            #
            # 1. Cosmetically, we set the CSS editing box's CSS class
            # to be 'hidden'. (We have some CSS that makes it not show
            # up.) SB: Not sure why we don't just remove the field...
            css_field = self.fields['css']
            css_field.label += ' (upgrade to enable this form field)'
            css_field.widget.attrs['readonly'] = True
            #
            # 2. In validation, we make sure that changing the CSS is
            # rejected as invalid if the site does not have permission
            # to do that.

    def clean_css(self):
        css = self.cleaned_data.get('css')
        # Does the current tier permit custom CSS? If so, return the data the
        # user submitted.
        if self.tier.custom_css:
            return css # no questions asked

        # We permit the value if it's the same as self.instance has:
        # SB: Leaving this for now, for backwards-compatibility, but again:
        # if css isn't allowed, we should probably not be storing it. This is
        # probably only here because we didn't remove the field on __init__.
        if self.instance.css == css:
            return css

        # Otherwise, reject the change.
        self.data['css'] = self.instance.css
        raise ValidationError(
            "To edit CSS for your site, you have to upgrade.")

class AuthorForm(_AuthorForm):
    def __init__(self, *args, **kwargs):
        _AuthorForm.__init__(self, *args, **kwargs)
        ## Add a note to the 'role' help text indicating how many admins
        ## are permitted with this kind of account.
        self.tier = Tier.objects.get(sitetierinfo__site=settings.SITE_ID)
        if self.tier.admin_limit is not None:
            # For backwards-compatibility, pretend the site owner (a
            # superuser) counts toward the limit.
            limit = self.tier.admin_limit + 1
            message = ('With a {tier_name}, you may have {limit} '
                       'administrator{s}.').format(tier_name=self.tier.name,
                                                   limit=limit,
                                                   s=pluralize(limit))
            self.fields['role'].help_text = message

    def clean_role(self):
        role = self.cleaned_data['role']

        # Nothing to check if they aren't being set to admin.
        if role != 'admin':
            return role

        # Nothing to check if there is no admin limit.
        if self.tier.admin_limit is None:
            return role

        # Nothing to check if the user is already an admin.
        if 'role' not in self.changed_data:
            return role

        # And finally, we're good if there's room for another admin.
        admin_count = self.site_settings.admins.exclude(is_superuser=True
                                              ).exclude(is_active=False
                                              ).count()
        if (admin_count + 1) <= self.tier.admin_limit:
            return role

        # For backwards-compatibility, pretend the site owner (a
        # superuser) counts toward the limit.
        limit = self.tier.admin_limit + 1
        raise ValidationError("You already have {limit} admin{s} in your "
                              "site. Upgrade to have access to more.".format(
                                        limit=limit, s=pluralize(limit)))


AuthorFormSet = modelformset_factory(User,
                                     form=AuthorForm,
                                     can_delete=True,
                                     extra=0)

class BulkEditVideoFormSet(_BulkEditVideoFormSet):

    def clean(self):
        tier = Tier.objects.get(sitetierinfo__site=settings.SITE_ID)
        self.approval_count = 0
        _BulkEditVideoFormSet.clean(self)
        if tier.video_limit is not None:
            video_count = Video.objects.filter(status=Video.ACTIVE,
                                               site=settings.SITE_ID
                                      ).count()
            remaining = tier.video_limit - video_count
            if remaining < 0:
                raise ValidationError('You already have {0} videos over your '
                                      'limit ({1}). Upgrade to approve '
                                      'more.'.format(-1 * remaining,
                                                     tier.video_limit))
            elif self.approval_count > remaining:
                raise ValidationError('You can only approve {0} videos, '
                                      'but tried to approve {1} instead. '
                                      'Upgrade to approve more.'.format(
                                      remaining, self.approval_count))

    def action_approve(self, form):
        if form.instance.status != Video.ACTIVE:
            self.approval_count += 1
        _BulkEditVideoFormSet.action_approve(self, form)

    def action_feature(self, form):
        if form.instance.status != Video.ACTIVE:
            self.approval_count += 1
        _BulkEditVideoFormSet.action_feature(self, form)

VideoFormSet = modelformset_factory(
    Video,
    form=BulkEditVideoForm,
    formset=BulkEditVideoFormSet,
    can_delete=True,
    extra=1)
