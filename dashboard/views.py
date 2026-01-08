from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from django.shortcuts import get_object_or_404
from .models import Patient, Record
from .serializers import (
    PatientSerializer, PatientDetailSerializer, 
    PatientCreateUpdateSerializer, RecordSerializer
)
from django.utils import timezone
from datetime import timedelta
from django.db.models.functions import TruncDate
from django.db.models import Count
from AIModel.models import DiagnosisResult


# ============ PATIENT VIEWS ============

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def patient_list_create(request):
    """
    GET: Get all patients for the authenticated user (with filters/sorting)
    POST: Create a new patient
    """
    
    if request.method == 'GET':
        # Get all patients created by the authenticated user
        patients = Patient.objects.filter(created_by=request.user)
        
        # Search by name
        search = request.query_params.get('search', None)
        if search:
            patients = patients.filter(
                Q(first_name__icontains=search) | 
                Q(last_name__icontains=search)
            )
        
        # Filter by age
        min_age = request.query_params.get('min_age', None)
        max_age = request.query_params.get('max_age', None)
        
        if min_age or max_age:
            from django.utils import timezone
            today = timezone.now().date()
            
            if max_age:
                # Calculate birth date for minimum age
                min_birth_date = today.replace(year=today.year - int(max_age) - 1)
                patients = patients.filter(date_of_birth__gte=min_birth_date)
            
            if min_age:
                # Calculate birth date for maximum age
                max_birth_date = today.replace(year=today.year - int(min_age))
                patients = patients.filter(date_of_birth__lte=max_birth_date)
        
        # Sorting
        sort_by = request.query_params.get('sort_by', 'created_at')
        order = request.query_params.get('order', 'desc')
        
        valid_sort_fields = {
            'name': 'last_name',
            'last_name': 'last_name',
            'first_name': 'first_name',
            'created_at': 'created_at',
            'last_visit': 'last_visit',
            'age': 'date_of_birth',  # Sort by DOB for age (inverse)
        }
        
        sort_field = valid_sort_fields.get(sort_by, 'created_at')
        
        if order == 'asc':
            patients = patients.order_by(sort_field)
        else:
            patients = patients.order_by(f'-{sort_field}')
        
        serializer = PatientSerializer(patients, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        serializer = PatientCreateUpdateSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            patient = serializer.save(created_by=request.user)
            return Response(
                PatientSerializer(patient).data,
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def patient_detail(request, pk):
    """
    GET: Get single patient info
    PUT/PATCH: Update patient
    DELETE: Delete patient
    """
    patient = get_object_or_404(Patient, pk=pk, created_by=request.user)
    
    if request.method == 'GET':
        serializer = PatientDetailSerializer(patient)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method in ['PUT', 'PATCH']:
        serializer = PatientCreateUpdateSerializer(
            patient,
            data=request.data,
            partial=(request.method == 'PATCH'),
            context={'request': request}
        )
        
        if serializer.is_valid():
            serializer.save()
            return Response(
                PatientDetailSerializer(patient).data,
                status=status.HTTP_200_OK
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        patient.delete()
        return Response(
            {'message': 'Patient deleted successfully.'},
            status=status.HTTP_204_NO_CONTENT
        )


# ============ RECORD VIEWS ============

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def record_list_create(request):
    """
    GET: Get all records (optionally filter by patient)
    POST: Create a new record
    """
    
    if request.method == 'GET':
        # Get records for patients created by the authenticated user
        records = Record.objects.filter(patient__created_by=request.user)
        
        # Filter by patient
        patient_id = request.query_params.get('patient_id', None)
        if patient_id:
            records = records.filter(patient_id=patient_id)
        
        # Filter by record type
        record_type = request.query_params.get('record_type', None)
        if record_type:
            records = records.filter(record_type=record_type)
        
        # Search by title or description
        search = request.query_params.get('search', None)
        if search:
            records = records.filter(
                Q(title__icontains=search) | 
                Q(description__icontains=search)
            )
        
        # Sorting
        sort_by = request.query_params.get('sort_by', 'visit_date')
        order = request.query_params.get('order', 'desc')
        
        valid_sort_fields = ['visit_date', 'created_at', 'record_type']
        sort_field = sort_by if sort_by in valid_sort_fields else 'visit_date'
        
        if order == 'asc':
            records = records.order_by(sort_field)
        else:
            records = records.order_by(f'-{sort_field}')
        
        serializer = RecordSerializer(records, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        # Verify that the patient belongs to the authenticated user
        patient_id = request.data.get('patient')
        if not patient_id:
            return Response(
                {'error': 'Patient ID is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        patient = get_object_or_404(Patient, pk=patient_id, created_by=request.user)
        
        serializer = RecordSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            record = serializer.save(created_by=request.user)
            return Response(
                RecordSerializer(record).data,
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def record_detail(request, pk):
    """
    GET: Get single record info
    PUT/PATCH: Update record
    DELETE: Delete record
    """
    record = get_object_or_404(
        Record, 
        pk=pk, 
        patient__created_by=request.user
    )
    
    if request.method == 'GET':
        serializer = RecordSerializer(record)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method in ['PUT', 'PATCH']:
        serializer = RecordSerializer(
            record,
            data=request.data,
            partial=(request.method == 'PATCH'),
            context={'request': request}
        )
        
        if serializer.is_valid():
            serializer.save()
            return Response(
                RecordSerializer(record).data,
                status=status.HTTP_200_OK
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        record.delete()
        return Response(
            {'message': 'Record deleted successfully.'},
            status=status.HTTP_204_NO_CONTENT
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def patient_records(request, patient_id):
    """
    Get all records for a specific patient
    """
    patient = get_object_or_404(Patient, pk=patient_id, created_by=request.user)
    records = Record.objects.filter(patient=patient)
    
    # Filter by record type
    record_type = request.query_params.get('record_type', None)
    if record_type:
        records = records.filter(record_type=record_type)
    
    serializer = RecordSerializer(records, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    """
    Get dashboard statistics
    """
    patients = Patient.objects.filter(created_by=request.user)
    records = Record.objects.filter(patient__created_by=request.user)
    
    from django.utils import timezone
    from datetime import timedelta
    
    today = timezone.now().date()
    last_month = today - timedelta(days=30)
    
    stats = {
        'total_patients': patients.count(),
        'total_records': records.count(),
        'patients_this_month': patients.filter(created_at__gte=last_month).count(),
        'records_this_month': records.filter(created_at__gte=last_month).count(),
        'recent_patients': PatientSerializer(
            patients.order_by('-created_at')[:5], 
            many=True
        ).data,
        'recent_visits': PatientSerializer(
            patients.filter(last_visit__isnull=False).order_by('-last_visit')[:5],
            many=True
        ).data,
    }
    
    return Response(stats, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def scans_activity(request):
    """
    Return daily scan counts for the authenticated user.
    Query params:
      - days (int): number of days back from today (default 30)
    Response: { data: [{date: 'YYYY-MM-DD', count: N}, ...] }
    """
    try:
        days = int(request.query_params.get('days', 30))
        if days < 1:
            days = 30

        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days - 1)

        # Include scans for the user OR scans without a user assigned
        qs = DiagnosisResult.objects.filter(
            uploaded_at__date__gte=start_date,
            uploaded_at__date__lte=end_date
        ).filter(
            Q(user=request.user) | Q(user__isnull=True)
        )

        daily_qs = qs.annotate(day=TruncDate('uploaded_at')).values('day').annotate(count=Count('id')).order_by('day')

        counts_map = {item['day'].isoformat(): item['count'] for item in daily_qs}

        # Fill missing dates with zeros
        data = []
        current = start_date
        while current <= end_date:
            dstr = current.isoformat()
            data.append({'date': dstr, 'count': counts_map.get(dstr, 0)})
            current = current + timedelta(days=1)

        return Response({'success': True, 'data': data}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)