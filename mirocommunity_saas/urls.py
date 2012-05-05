from django.conf.urls.defaults import patterns, include, url

from mirocommunity_saas.admin.forms import (
    EditSettingsForm, AuthorForm, AuthorFormSet, VideoFormSet)

urlpatterns = patterns('mirocommunity_saas.views',
    url(r'^newsletter/$', 'newsletter', name='localtv_newsletter'))

urlpatterns += patterns('mirocommunity_saas.admin.views',
    (r'^admin/$',
     'index', {}, 'localtv_admin_index'),
    (r'^admin/upgrade/$',
     'upgrade', {}, 'localtv_admin_tier'),
    url(r'^admin/paypal/', include('paypal.standard.ipn.views'),),
    (r'^admin/paypal_return/(?P<payment_secret>.+)/(?P<target_tier_name>[a-z_]+?)/$',
     'paypal_return', {}, 'localtv_admin_paypal_return'),
    (r'^admin/begin_free_trial/(?P<payment_secret>.+?)/$',
     'begin_free_trial', {}, 'localtv_admin_begin_free_trial'),
    (r'^admin/downgrade_confirm/$',
     'downgrade_confirm', {}, 'localtv_admin_downgrade_confirm'),
    (r'^admin/confirmed_change_tier/$',
     'confirmed_change_tier', {}, 'localtv_admin_confirmed_change_tier'),
    (r'^admin/ipn_endpoint/(?P<payment_secret>.+?)/$',
     'ipn_endpoint', {}, 'localtv_admin_ipn_endpoint'),
                       )

urlpatterns += patterns(
    'mirocommunity_saas.admin.approve_reject_views',
    (r'^admin/actions/approve_video/$', 'approve_video',
     {}, 'localtv_admin_approve_video'),
    (r'^admin/actions/feature_video/$', 'feature_video',
     {}, 'localtv_admin_feature_video'),
    (r'^admin/actions/approve_all/$', 'approve_all',
     {}, 'localtv_admin_approve_all'),
    )

urlpatterns += patterns(
    'mirocommunity_saas.admin.design_views',
    (r'^admin/settings/newsletter/$', 'newsletter_settings',
     {}, 'localtv_admin_newsletter_settings'))

urlpatterns += patterns(
    'mirocommunity_saas.admin.livesearch_views',
    (r'^admin/add/approve/$', 'approve',
     {}, 'localtv_admin_search_video_approve')
)
urlpatterns += patterns('localtv.admin',
    (r'^admin/settings/$', 'design_views.edit_settings',
     {'form_class': EditSettingsForm}, 'localtv_admin_settings'),
    (r'^admin/users/$', 'user_views.users',
     {'formset_class': AuthorFormSet,
      'form_class': AuthorForm}, 'localtv_admin_users'),
    (r'^admin/bulk_edit/$', 'bulk_edit_views.bulk_edit',
     {'formset_class': VideoFormSet}, 'localtv_admin_bulk_edit'))

urlpatterns += patterns(
    '',
    (r'', include('localtv.urls'))
)


