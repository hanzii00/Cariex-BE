from rest_framework import serializers
from .models import Patient, Record

class RecordSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    
    class Meta:
        model = Record
        fields = [
            'id', 'patient', 'patient_name', 'created_by', 'created_by_name',
            'record_type', 'title', 'description', 'diagnosis', 
            'prescription', 'notes', 'visit_date', 'follow_up_date',
            'attachments', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']
    
    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class PatientSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    age = serializers.IntegerField(read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = Patient
        fields = [
            'id', 'created_by', 'created_by_name', 'first_name', 'last_name', 
            'full_name', 'date_of_birth', 'age', 'gender', 'email', 'phone', 
            'address', 'blood_type', 'allergies', 'emergency_contact_name', 
            'emergency_contact_phone', 'created_at', 'updated_at', 'last_visit'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at', 'last_visit']
    
    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class PatientDetailSerializer(PatientSerializer):
    """Extended serializer with records"""
    records = RecordSerializer(many=True, read_only=True)
    records_count = serializers.SerializerMethodField()
    
    class Meta(PatientSerializer.Meta):
        fields = PatientSerializer.Meta.fields + ['records', 'records_count']
    
    def get_records_count(self, obj):
        return obj.records.count()


class PatientCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating patients"""
    
    class Meta:
        model = Patient
        fields = [
            'first_name', 'last_name', 'date_of_birth', 'gender', 
            'email', 'phone', 'address', 'blood_type', 'allergies',
            'emergency_contact_name', 'emergency_contact_phone'
        ]
    
    def validate_date_of_birth(self, value):
        """Ensure date of birth is not in the future"""
        from django.utils import timezone
        if value > timezone.now().date():
            raise serializers.ValidationError("Date of birth cannot be in the future.")
        return value