from rest_framework import serializers


class PlanRequestSerializer(serializers.Serializer):
    origin = serializers.CharField(max_length=300)
    destination = serializers.CharField(max_length=300)
    departure = serializers.DateTimeField()
    load_weight_lb = serializers.FloatField(min_value=0)
    sample_interval_miles = serializers.ChoiceField(choices=[10, 25, 50], default=25)
