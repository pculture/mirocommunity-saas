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


OVER_LIMIT_ERROR = ("You've hit your video limit ({limit} videos). You will "
                    "need to upgrade to approve {video_text}.")
UNDER_LIMIT_ERROR = ("You only have {remaining} videos left before you hit "
                     "your limit ({limit} videos). You will need to upgrade "
                     "to approve {video_text}.")


def _video_limit_error(approve_count, remaining, limit):
    if approve_count == 1:
        video_text = "that video"
    else:
        video_text = "those {0} videos".format(approve_count)
    if remaining <= 0:
        return OVER_LIMIT_ERROR.format(video_text=video_text, limit=limit)
    else:
        return UNDER_LIMIT_ERROR.format(video_text=video_text,
                                        remaining=remaining,
                                        limit=limit)


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
            tier = get_object_or_404(Tier,
                                     sitetierinfo__site=settings.SITE_ID)
            # If the site would exceed its video allotment, then fail with an
            # HTTP 402 and a clear message about why.
            if tier.video_limit is not None:
                videos = Video.objects.filter(status=Video.ACTIVE,
                                              site=settings.SITE_ID)
                remaining = tier.video_limit - videos.count()
                if remaining < 1:
                    return HttpResponse(
                        content=_video_limit_error(1, remaining,
                                                   tier.video_limit),
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

    tier = get_object_or_404(Tier, sitetierinfo__site=settings.SITE_ID)
    if tier.video_limit is not None:
        videos = Video.objects.filter(status=Video.ACTIVE,
                                      site=settings.SITE_ID)
        remaining = tier.video_limit - videos.count()
        need = len(page.object_list)

        if need > remaining:
            return HttpResponse(content=_video_limit_error(need, remaining,
                                                           tier.video_limit),
                                status=402)

    return _approve_all(request)
