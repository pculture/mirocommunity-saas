Congratulations, {{ user.first_name|default:user.username }}!

Your new Miro Community site is ready to go at http://{{ site.domain }}/. As soon as you arrive, log in and visit the [admin dashboard](http://{{ site.domain }}/{% url localtv_admin_index %}) to get started building your site. Remember that your username and password are case sensitive.

You can learn more about using Miro Community from the [User Manual](http://support.mirocommunity.org/solution/categories/13505){% if tier.custom_domain %} - or learn [how to use your site at a custom domain](http://develop.participatoryculture.org/index.php/MiroCommunity/CustomDomain){% if tier.custom_themes %} and [how to use custom templates](http://develop.participatoryculture.org/index.php/MiroCommunity/Theming){% endif %}{% endif %}.

You currently have a {{ tier.name|capfirst }} account for http://{{ site.domain }}/, which includes:

* Your site with the logo & background of your choice{% if tier.custom_domain %}
* Custom domain{% endif %}{% if tier.custom_css %}
* Custom css{% endif %}
* **{{ tier.video_limit }}** video limit
* **{% if tier.admin_limit == 0 or tier.admin_limit %}{{ tier.admin_limit|add:1 }}{% else %}Unlimited{% endif %}** administrator accounts{% if tier.ads_allowed %}
* You can run advertising{% endif %}{% if tier.custom_themes %}
* Fully custom templating{% endif %}

{% if tier_info.in_free_trial %}Your 30-day free trial lasts until midnight on {{ tier_info.get_free_trial_end|date:"F j, Y" }}. If
you don't want to continue using Miro Community at a paid level, just switch to
"basic" before the trial ends and you won't be charged (we'll email you 5 days
before the trial ends to remind you). Otherwise, you'll pay just ${{ tier_info.tier.price }}/month
for the service as long as your account is open. You can upgrade or downgrade at
any time at http://{{ site.domain}}{% url localtv_admin_tier %}
{% endif %}

Still have questions? Don't hesitate to get in touch:
<support@mirocommunity.org>.

Enjoy!

-- The Miro Community Team

[Follow us on Twitter](http://twitter.com/mirocommunity)