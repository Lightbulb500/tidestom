from django import forms

class TidesTargetForm(forms.Form):
    humanclass = forms.CharField(max_length=50, required=True, label="Supernova Type")
    humanclass_other = forms.FloatField(required=False, label="Redshift")
    humanclass_subclass = forms.CharField(max_length=100, required=False, label="Subtype")
    comments = forms.CharField(widget=forms.Textarea, required=False, label="Comments")

    def clean(self):
        cleaned_data = super().clean()
        humanclass = cleaned_data.get('humanclass')
        humanclass_other = cleaned_data.get('humanclass_other')

        # Validate that 'humanclass_other' is required when 'humanclass' is "Other"
        if humanclass == 'Other' and not humanclass_other:
            self.add_error('humanclass_other', 'This field is required when "Other" is selected.')

        return cleaned_data