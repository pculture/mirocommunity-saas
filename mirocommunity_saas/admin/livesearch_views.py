from django.http import HttpResponse

from localtv.admin.livesearch import views
from localtv.decorators import require_site_admin, referrer_redirect

from mirocommunity_saas.models import TierInfo

class LiveSearchApproveVideoView(views.LiveSearchApproveVideoView):

    def get(self, request, **kwargs):
        if not request.GET.get('queue'):
            tier_info = TierInfo.objects.get_current()
            if not tier_info.get_tier().can_add_more_videos():
                return HttpResponse(
                    content="You are over the video limit. You "
                    "will need to upgrade to approve "
                    "that video.", status=402)

        return views.LiveSearchApproveVideoView.get(self, request, **kwargs)

approve = referrer_redirect(require_site_admin(
        LiveSearchApproveVideoView.as_view()))
