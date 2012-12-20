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

from django.core.urlresolvers import reverse
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from uploadtemplate.models import Theme
from uploadtemplate.views import AdminView

from mirocommunity_saas.models import SiteTierInfo


class UploadtemplateAdmin(AdminView):
	def post(self, *args, **kwargs):
		tier = SiteTierInfo.objects.get_current().tier
		if not tier.custom_themes:
			return HttpResponseForbidden("Eek, you may not upload templates.")
		return super(UploadtemplateAdmin, self).post(*args, **kwargs)

	def get_context_data(self, **kwargs):
		context = super(UploadtemplateAdmin, self).get_context_data(**kwargs)
		tier = SiteTierInfo.objects.get_current().tier
		if not tier.custom_themes:
			# Only display non-custom themes as options.
			context['themes'] = Theme.objects.filter(bundled=True)
		return context


def set_default(request, theme_id):
    """
    This sets a theme as the default.

    If custom themes are disabled, users will only permitted to select a
    "bundled" theme.

    """
    theme = get_object_or_404(Theme, pk=theme_id)
    tier = SiteTierInfo.objects.get_current().tier

    if not tier.custom_themes:
        return HttpResponseForbidden("Eek, you may not set this theme as your current theme.")

    # Ok, the theme is fine and the person has permission.
    theme.set_as_default()
    return HttpResponseRedirect(reverse('uploadtemplate-index'))
