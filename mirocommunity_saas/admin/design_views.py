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
from django.http import Http404

from mirocommunity_saas.models import Tier

from localtv.decorators import require_site_admin

from localtv.admin.design_views import (
    newsletter_settings as _newsletter_settings)

@require_site_admin
def newsletter_settings(request):
    tier = Tier.objects.get(sitetierinfo__site=settings.SITE_ID)
    if not tier.newsletter:
        raise Http404

    return _newsletter_settings(request)
