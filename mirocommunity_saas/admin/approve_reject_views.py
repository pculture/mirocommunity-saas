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

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from localtv.models import Video, SiteSettings
from localtv.decorators import require_site_admin
from localtv.admin.approve_reject_views import (
    approve_video as _approve_video,
    feature_video as _feature_video,
    approve_all as _approve_all,
    get_video_paginator)

from mirocommunity_saas.models import Tier


VIDEO_LIMIT_ERROR = ("You are over the video limit. You will need to upgrade "
                     "to approve that video.")


def _video_limit_wrapper(view_func):
    """
    This is a quick & dirty wrapper to add video limits to the approve_video
    and feature_video views.

    """
    @wraps(view_func)
    def wrapper(request):
        video = get_object_or_404(Video,
                                  id=request.GET.get('video_id'),
                                  site=settings.SITE_ID)
        if video.status != Video.ACTIVE:
            tier = Tier.objects.get(sitetierinfo__site=settings.SITE_ID)
            # If the site would exceed its video allotment, then fail with an
            # HTTP 402 and a clear message about why.
            videos = Video.objects.filter(status=Video.ACTIVE,
                                          site=settings.SITE_ID)
            remaining = tier.video_limit - videos.count()
            if remaining < 1:
                return HttpResponse(
                    content=VIDEO_LIMIT_ERROR,
                    status=402)
        return view_func(request)
    return wrapper


approve_video = require_site_admin(_video_limit_wrapper(_approve_video))
feature_video = require_site_admin(_video_limit_wrapper(_feature_video))


@require_site_admin
def approve_all(request):
    # This view approves all the videos on the current page.
    site_settings = SiteSettings.objects.get_current()

    video_paginator = get_video_paginator(site_settings)
    try:
        page = video_paginator.page(int(request.GET.get('page', 1)))
    except Exception:
        # let the other view handle it
        return _approve_all(request)

    tier = Tier.objects.get(sitetierinfo__site=settings.SITE_ID)
    videos = Video.objects.filter(status=Video.ACTIVE, site=settings.SITE_ID)
    remaining = tier.video_limit - videos.count()
    need = len(page.object_list)

    if need > remaining:
        return HttpResponse(content=("You are trying to approve {need} videos"
                                     " at a time.  However, you can approve "
                                     "only {remaining} more videos under your"
                                     " video limit. Please upgrade your "
                                     "account to increase your limit, or "
                                     "unapprove some older videos to make "
                                     "space for newer ones.").format(
                                         need=need, remaining=remaining),
                            status=402)

    return _approve_all(request)
