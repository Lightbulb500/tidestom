from django.views.generic.detail import DetailView
from django_filters.views import FilterView
from django.utils import timezone
from django.views.generic.edit import FormView
from django.db import models
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from guardian.mixins import PermissionListMixin
from tom_targets.models import Target
from tom_dataproducts.models import DataProduct
from datetime import timedelta
from collections import Counter
from custom_code.models import MirroredTidesTarget,  HumanClassification, PipelineClassificationGlobal  
from custom_code.forms import TidesTargetForm
import psycopg2
from django.conf import settings
from django.db import transaction
from django.views.generic.list import ListView
from django.utils.timezone import now
from custom_code.models import TidesSpec
import logging

logger = logging.getLogger(__name__)

class LatestView(ListView):
    template_name = 'latest.html'
    paginate_by = 200
    model = TidesSpec
    context_object_name = 'targets'

    def get_queryset(self):
        # Default range: last 30 days
        days_range = self.request.GET.get('days_range', 30)
        date_threshold = now() - timedelta(days=int(days_range))

        # Query tides_spec for objects observed within the range
        return TidesSpec.objects.filter(obs_date__gte=date_threshold).order_by('-obs_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['default_days_range'] = self.request.GET.get('days_range', 30)

        # Get matching MirroredTidesTarget objects by tides_id
        tides_ids = [spec.tides_id for spec in context['targets']]
        target_map = {
            t.tides_id: t for t in MirroredTidesTarget.objects.filter(tides_id__in=tides_ids)
        }

        # Attach the corresponding MirroredTidesTarget to each TidesSpec
        for spec in context['targets']:
            spec.mirrored_target = target_map.get(spec.tides_id)

        return context

class MyTargetDetailView(DetailView):
    model = MirroredTidesTarget
    template_name = 'target_detail.html'
    context_object_name = 'target'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        target = self.get_object()
        logger.info(f"Target tides_id: {target.tides_id}")
        # Log the target object
        logger.info(f"Target object: {target}")

        # Query human classifications for this target
        submissions = HumanClassification.objects.filter(tides_id=target.tides_id)

        # Aggregate the most common classification
        if submissions.exists():
            aggregation = HumanClassification.aggregate_human_tidesclass(target.tides_id)
            context['aggregated_human_class'] = aggregation
        else:
            context['aggregated_human_class'] = None

        # Add all individual submissions to the context
        context['human_classifications'] = submissions.order_by('-created')

        # Query auto-classifications for this target
        try:
            auto_classifications = PipelineClassificationGlobal.objects.filter(
                tides_target__tides_id=target.tides_id  # Correctly traverse the foreign key
            ).order_by('-probability')
            logger.info(f"Auto-classifications query successful: {auto_classifications}")
        except Exception as e:
            logger.error(f"Error querying auto-classifications: {e}")
            auto_classifications = []

        context['auto_classifications'] = auto_classifications

        return context

class SubmitClassificationView(FormView):
    form_class = TidesTargetForm

    def form_valid(self, form):
        # Get the target object
        target = get_object_or_404(MirroredTidesTarget, id=self.kwargs['target_id'])

        # Prepare data for insertion into human_classifications table
        classification_data = {
            'tides_id': target.tides_id,  # Assuming TidesTarget has a tides_id field
            'obs_id': None,  # Replace with actual observation ID if available
            'person_id': self.request.user.id,
            'sn_type': form.cleaned_data['tidesclass'],
            'sn_z': form.cleaned_data.get('tidesclass_other'),
            'sn_subtype': form.cleaned_data.get('tidesclass_subclass'),
            'comments': form.cleaned_data.get('comments', ''),
            'created': now(),
        }

        # Insert data into human_classifications table using Django ORM
        try:
            with transaction.atomic(using='tides_db'):  # Use the database router
                HumanClassification.objects.create(**classification_data)
            self.request.session['success_message'] = "Classification submitted successfully!"
        except Exception as e:
            self.request.session['error_message'] = f"Failed to submit classification: {e}"

        return redirect('target_detail', pk=self.kwargs['target_id'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['object'] = get_object_or_404(TidesTarget, id=self.kwargs['target_id'])
        context['form'] = self.get_form()
        return context
    
from django.http import JsonResponse
from custom_code.classification_list import CLASSIFICATIONS

def get_subclasses(request):
    main_class_name = request.GET.get('main_class')
    subclasses = CLASSIFICATIONS.get(main_class_name, [])
    return JsonResponse(subclasses, safe=False)

