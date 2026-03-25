import logging
import re

from django.template import Context, Template
from django.template.exceptions import TemplateSyntaxError

logger = logging.getLogger(__name__)


class TemplateRenderService:
    """Service for rendering notification templates with context variables."""

    @staticmethod
    def render_template(template_id, context, organization=None):
        """Render a template with the given context variables.

        Args:
            template_id: UUID of the NotificationTemplate.
            context: Dictionary of template variables.
            organization: Organization for scoping the lookup.

        Returns:
            Dictionary with rendered subject, body, and body_html.
        """
        from .models import NotificationTemplate

        filters = {"pk": template_id, "is_active": True}
        if organization:
            filters["organization"] = organization

        try:
            template = NotificationTemplate.objects.get(**filters)
        except NotificationTemplate.DoesNotExist:
            raise ValueError(f"Template {template_id} not found or inactive.")

        # Fill in defaults for missing variables
        for variable in template.variables.all():
            if variable.name not in context:
                if variable.is_required and not variable.default_value:
                    logger.warning(
                        f"Required variable '{variable.name}' missing for template {template.name}"
                    )
                context.setdefault(variable.name, variable.default_value)

        rendered_subject = TemplateRenderService._render_string(
            template.subject, context
        )
        rendered_body = TemplateRenderService._render_string(
            template.body_text, context
        )
        rendered_body_html = TemplateRenderService._render_string(
            template.body_html, context
        )

        return {
            "subject": rendered_subject,
            "body": rendered_body,
            "body_html": rendered_body_html,
            "template_id": str(template.id),
            "template_name": template.name,
            "version": template.current_version,
        }

    @staticmethod
    def _render_string(template_string, context):
        """Render a template string with the given context.

        Supports both Django template syntax and simple {{variable}} substitution.
        """
        if not template_string:
            return ""

        # Convert {{variable}} to Django template syntax {% templatetag %}
        converted = re.sub(r"\{\{(\w+)\}\}", r"{{ \1 }}", template_string)

        try:
            django_template = Template(converted)
            rendered = django_template.render(Context(context))
            return rendered
        except TemplateSyntaxError as e:
            logger.error(f"Template syntax error: {e}")
            # Fall back to simple string substitution
            return TemplateRenderService._simple_render(template_string, context)

    @staticmethod
    def _simple_render(template_string, context):
        """Simple string-based template rendering as a fallback."""
        result = template_string
        for key, value in context.items():
            result = result.replace(f"{{{{{key}}}}}", str(value))
        return result

    @staticmethod
    def validate_template(template_string, variables=None):
        """Validate that a template string is syntactically correct.

        Returns:
            Tuple of (is_valid, error_message, detected_variables).
        """
        pattern = r"\{\{(\w+)\}\}"
        detected = set(re.findall(pattern, template_string))

        converted = re.sub(pattern, r"{{ \1 }}", template_string)
        try:
            Template(converted)
        except TemplateSyntaxError as e:
            return False, str(e), list(detected)

        if variables:
            missing = set(variables) - detected
            if missing:
                return True, f"Unused variables defined: {missing}", list(detected)

        return True, "", list(detected)
