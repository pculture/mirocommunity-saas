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
from django.http import HttpResponse

from localtv.admin.livesearch.views import LiveSearchApproveVideoView
from localtv.decorators import require_site_admin, referrer_redirect
from localtv.models import Video

from mirocommunity_saas.models import Tier

class TierLiveSearchApproveVideoView(LiveSearchApproveVideoView):

    def get(self, request, **kwargs):
        if not request.GET.get('queue'):
            tier = Tier.objects.get(sitetierinfo__site=settings.SITE_ID)
            if tier.video_limit is not None:
                video_count = Video.objects.filter(status=Video.ACTIVE,
                                                   site=settings.SITE_ID
                                          ).count()
                if video_count + 1 > tier.video_limit:
                    return HttpResponse(
                        content="You are over the video limit. You "
                        "will need to upgrade to approve "
                        "that video.", status=402)

        return LiveSearchApproveVideoView.get(self, request, **kwargs)

approve = referrer_redirect(require_site_admin(
        TierLiveSearchApproveVideoView.as_view()))
