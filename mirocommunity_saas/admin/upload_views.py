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

from functools import wraps

from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from localtv.admin import upload_views
from localtv.decorators import require_site_admin
from uploadtemplate.models import Theme
from uploadtemplate.views import ThemeIndexView

from mirocommunity_saas.models import SiteTierInfo


def require_custom_themes(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        tier = SiteTierInfo.objects.get_current().tier
        if not tier.custom_themes:
            raise Http404
        return view_func(*args, **kwargs)
    return wrapper


class UploadtemplateAdmin(ThemeIndexView):
	def get_context_data(self, **kwargs):
		context = super(UploadtemplateAdmin, self).get_context_data(**kwargs)
		tier = SiteTierInfo.objects.get_current().tier
		if not tier.custom_themes:
			context['themes'] = Theme.objects.none()
		return context


index = require_custom_themes(require_site_admin(UploadtemplateAdmin.as_view()))
update = require_custom_themes(upload_views.update)
create = require_custom_themes(upload_views.create)
delete = require_custom_themes(upload_views.delete)
set_default = require_custom_themes(upload_views.set_default)
unset_default = require_custom_themes(upload_views.unset_default)
