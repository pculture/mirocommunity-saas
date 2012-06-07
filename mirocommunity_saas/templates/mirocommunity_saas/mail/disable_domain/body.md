{% if tier_info.site_name %}
The site called {{ tier_info.site_name }} used to be at {{ site.domain }}, but they've downgraded. As a result, their domain will be reset.
{% else %}
{{ site.domain }} has downgraded.
{% endif %}

If there are any adjustments to make because of this, now would be the time.