from django.db import models
from tom_targets.base_models import BaseTarget
from django.contrib.auth.models import User
from django.utils.timezone import now
from collections import Counter
from django.db.models import JSONField  # Import JSONField for PostgreSQL

class TidesClass(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name

class TidesClassSubClass(models.Model):
    main_class = models.ForeignKey(TidesClass, on_delete=models.CASCADE, related_name='sub_classes')
    sub_class = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.main_class.name} - {self.sub_class}"

class TidesTarget(BaseTarget):
    """
    A target with fields defined by a user.
    """
    TIDES_CLASS_CHOICES = [
        ('SN', 'SN'),
        ('SNI','SNI'),
        ('SNIa', 'SNIa'),
        ('SNIbc', 'SNIbc'),
        ('SNIb', 'SNIb'),
        ('SNIc', 'SNIc'),
        ('SNId', 'SNId'),
        ('SNIe', 'SNIe'),
        ('SNII', 'SNII'),
        ('SLSN-I', 'SLSN-I'),
        ('SLSN-II', 'SLSN-II'),
        ('TDE', 'TDE'),
        ('KN', 'KN'),
        ('AGN', 'AGN'),
        ('LRN', 'LRN'),
        ('CV', 'CV'),
        ('LBV', 'LBV'),
        ('Other', 'Other'),
    ]

    # Existing fields
    tidesclass = models.CharField(max_length=50, choices=TIDES_CLASS_CHOICES, verbose_name='TiDES Classification', default='SN')
    tidesclass_other = models.CharField(max_length=100, blank=True, null=True, verbose_name='TiDES Classification (Other)')
    tidesclass_subclass = models.ForeignKey(TidesClassSubClass, on_delete=models.SET_NULL, blank=True, null=True, verbose_name='TiDES Sub-classification')

    # Replace individual auto classification fields with a JSONField
    auto_tidesclassifications = JSONField(blank=True, null=True, verbose_name='Auto TiDES Classifications')

    human_tidesclass = models.CharField(max_length=50, choices=TIDES_CLASS_CHOICES, verbose_name='Human TiDES Classification', blank=True, null=True)
    human_tidesclass_other = models.CharField(max_length=100, blank=True, null=True, verbose_name='Human TiDES Classification (Other)')
    human_tidesclass_subclass = models.ForeignKey(TidesClassSubClass, on_delete=models.SET_NULL, blank=True, null=True, related_name='human_subclass', verbose_name='Human TiDES Sub-classification')
    
    def aggregate_human_tidesclass(self):
        submissions = self.human_classifications.all()
        if not submissions:
            return None

        # Aggregate the most common classification
        tidesclass_counts = Counter(sub.tidesclass for sub in submissions)
        most_common_class, count = tidesclass_counts.most_common(1)[0]

        return {
            'most_common_class': most_common_class,
            'count': count,
            'total_submissions': len(submissions),
        }
    
    class Meta:
        verbose_name = "target"
        permissions = (
            ('view_target', 'View Target'),
            ('add_target', 'Add Target'),
            ('change_target', 'Change Target'),
            ('delete_target', 'Delete Target'),
        )
class HumanTidesClassSubmission(models.Model):
    target = models.ForeignKey(TidesTarget, on_delete=models.CASCADE, related_name='human_classifications')
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Submitted By')
    tidesclass = models.CharField(max_length=50, choices=TidesTarget.TIDES_CLASS_CHOICES, verbose_name='Human TiDES Classification')
    tidesclass_other = models.CharField(max_length=100, blank=True, null=True, verbose_name='Human TiDES Classification (Other)')
    tidesclass_subclass = models.ForeignKey(TidesClassSubClass, on_delete=models.SET_NULL, blank=True, null=True, verbose_name='Human TiDES Sub-classification')
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='Submission Time')  # Automatically set timestamp

    def __str__(self):
        return f"{self.user.username} - {self.target.name} - {self.tidesclass}"
