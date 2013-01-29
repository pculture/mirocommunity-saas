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

from django.http import Http404

from mirocommunity_saas.models import SiteTierInfo


def themes_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        tier = SiteTierInfo.objects.get_current().tier
        if not tier.custom_themes:
            raise Http404
        return view_func(*args, **kwargs)
    return wrapper
