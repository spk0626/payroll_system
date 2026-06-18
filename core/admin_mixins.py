class ActionLabelMixin:
    """Use a real empty label for Django admin bulk-action dropdowns."""

    def get_action_choices(self, request, default_choices=None):
        default_choices = default_choices or [("", "Select an action...")]
        choices = super().get_action_choices(request, default_choices)
        if choices:
            choices[0] = ("", "Select an action...")
        return choices
