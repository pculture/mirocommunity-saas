Hi there!

Just a heads up that there was a problem setting the tier for {{ site.domain }}. {% if payment > 0 %}We received an IPN for a payment of {{ payment }}{% else %}We received an expiration IPN and tried to switch to the free tier{% endif %}, but {% if not_found %}none{% endif %}{% if multiple_found %}more than one{% endif %} of the available tiers {% if not_found %}have{% endif %}{% if multiple_found %}has{% endif %} that price.

The current tier is {{ tier.name }} ({{ tier.slug }}).{% if tier_info.site_name %} The current site name is {{ tier_info.site_name }}.{% endif %}

Check it out.