from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Avg, Count, Q
import json
import traceback

from AIModel.models import DiagnosisResult
from .models import (
    ValidationStatus, DentistFeedback, FeedbackCategory,
    FeedbackComment, FeedbackAttachment
)


@require_http_methods(["POST"])
def submit_feedback(request, diagnosis_id):
    """
    Submit dentist feedback on a diagnosis
    """
    try:
        if not request.user.is_authenticated:
            return JsonResponse({
                'success': False,
                'error': 'Authentication required'
            }, status=401)
        
        diagnosis = get_object_or_404(DiagnosisResult, id=diagnosis_id)
        
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)
        
        if 'is_correct' not in data:
            return JsonResponse({
                'success': False,
                'error': 'is_correct field is required'
            }, status=400)
        
        # Create feedback
        feedback = DentistFeedback.objects.create(
            diagnosis=diagnosis,
            dentist=request.user,
            is_correct=data['is_correct'],
            corrected_has_caries=data.get('corrected_has_caries'),
            corrected_severity=data.get('corrected_severity'),
            feedback_text=data.get('feedback_text', ''),
            corrected_boxes=data.get('corrected_boxes'),
            ai_performance_rating=data.get('ai_performance_rating'),
            clinical_findings=data.get('clinical_findings', ''),
            recommended_treatment=data.get('recommended_treatment', ''),
            confidence_level=data.get('confidence_level', 'high')
        )
        
        # Add categories
        categories = data.get('categories', [])
        for category_type in categories:
            FeedbackCategory.objects.create(
                feedback=feedback,
                category=category_type,
                notes=data.get(f'{category_type}_notes', '')
            )
        
        # Update or create validation status
        validation, created = ValidationStatus.objects.get_or_create(
            diagnosis=diagnosis,
            defaults={
                'validated_by': request.user,
                'validated_at': timezone.now()
            }
        )
        
        if data['is_correct']:
            validation.validation_status = 'approved'
        elif data.get('corrected_severity') or data.get('corrected_has_caries') is not None:
            validation.validation_status = 'corrected'
        else:
            validation.validation_status = 'rejected'
        
        validation.validated_by = request.user
        validation.validated_at = timezone.now()
        validation.save()
        
        return JsonResponse({
            'success': True,
            'feedback_id': feedback.id,
            'diagnosis_id': diagnosis_id,
            'validation_status': validation.validation_status,
            'message': 'Feedback submitted successfully'
        })
        
    except Exception as e:
        print(f"Error in submit_feedback: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def get_feedback(request, diagnosis_id):
    """
    Get all feedback for a specific diagnosis
    """
    try:
        diagnosis = get_object_or_404(DiagnosisResult, id=diagnosis_id)
        feedbacks = DentistFeedback.objects.filter(diagnosis=diagnosis)
        
        feedback_list = []
        for feedback in feedbacks:
            categories = [
                {
                    'category': cat.category,
                    'notes': cat.notes
                }
                for cat in feedback.categories.all()
            ]
            
            comments = [
                {
                    'id': comment.id,
                    'author': comment.author.username,
                    'text': comment.comment_text,
                    'created_at': comment.created_at.isoformat()
                }
                for comment in feedback.comments.all()
            ]
            
            feedback_list.append({
                'id': feedback.id,
                'dentist': feedback.dentist.username if feedback.dentist else 'Anonymous',
                'is_correct': feedback.is_correct,
                'corrected_has_caries': feedback.corrected_has_caries,
                'corrected_severity': feedback.corrected_severity,
                'feedback_text': feedback.feedback_text,
                'corrected_boxes': feedback.corrected_boxes,
                'ai_performance_rating': feedback.ai_performance_rating,
                'clinical_findings': feedback.clinical_findings,
                'recommended_treatment': feedback.recommended_treatment,
                'confidence_level': feedback.confidence_level,
                'categories': categories,
                'comments': comments,
                'created_at': feedback.created_at.isoformat(),
                'updated_at': feedback.updated_at.isoformat()
            })
        
        # Get validation status
        try:
            validation = ValidationStatus.objects.get(diagnosis=diagnosis)
            validation_data = {
                'status': validation.validation_status,
                'validated_by': validation.validated_by.username if validation.validated_by else None,
                'validated_at': validation.validated_at.isoformat() if validation.validated_at else None
            }
        except ValidationStatus.DoesNotExist:
            validation_data = {'status': 'pending'}
        
        return JsonResponse({
            'success': True,
            'diagnosis_id': diagnosis_id,
            'feedback_count': len(feedback_list),
            'feedbacks': feedback_list,
            'diagnosis': {
                'severity': diagnosis.severity,
                'confidence': diagnosis.confidence_score,
                'has_caries': diagnosis.has_caries
            },
            'validation': validation_data
        })
        
    except Exception as e:
        print(f"Error in get_feedback: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["PUT"])
def update_feedback(request, feedback_id):
    """
    Update existing feedback
    """
    try:
        if not request.user.is_authenticated:
            return JsonResponse({
                'success': False,
                'error': 'Authentication required'
            }, status=401)
        
        feedback = get_object_or_404(DentistFeedback, id=feedback_id)
        
        if feedback.dentist != request.user and not request.user.is_staff:
            return JsonResponse({
                'success': False,
                'error': 'Not authorized to update this feedback'
            }, status=403)
        
        data = json.loads(request.body)
        
        # Update fields
        updatable_fields = [
            'is_correct', 'corrected_has_caries', 'corrected_severity',
            'feedback_text', 'corrected_boxes', 'ai_performance_rating',
            'clinical_findings', 'recommended_treatment', 'confidence_level'
        ]
        
        for field in updatable_fields:
            if field in data:
                setattr(feedback, field, data[field])
        
        feedback.save()
        
        return JsonResponse({
            'success': True,
            'feedback_id': feedback_id,
            'message': 'Feedback updated successfully'
        })
        
    except Exception as e:
        print(f"Error in update_feedback: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["DELETE"])
def delete_feedback(request, feedback_id):
    """
    Delete feedback
    """
    try:
        if not request.user.is_authenticated:
            return JsonResponse({
                'success': False,
                'error': 'Authentication required'
            }, status=401)
        
        feedback = get_object_or_404(DentistFeedback, id=feedback_id)
        
        if feedback.dentist != request.user and not request.user.is_staff:
            return JsonResponse({
                'success': False,
                'error': 'Not authorized to delete this feedback'
            }, status=403)
        
        diagnosis = feedback.diagnosis
        feedback.delete()
        
        # Update validation status if no more feedback
        if not DentistFeedback.objects.filter(diagnosis=diagnosis).exists():
            try:
                validation = ValidationStatus.objects.get(diagnosis=diagnosis)
                validation.validation_status = 'pending'
                validation.validated_by = None
                validation.validated_at = None
                validation.save()
            except ValidationStatus.DoesNotExist:
                pass
        
        return JsonResponse({
            'success': True,
            'message': 'Feedback deleted successfully'
        })
        
    except Exception as e:
        print(f"Error in delete_feedback: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["POST"])
def add_comment(request, feedback_id):
    """
    Add a comment to feedback for discussion
    """
    try:
        if not request.user.is_authenticated:
            return JsonResponse({
                'success': False,
                'error': 'Authentication required'
            }, status=401)
        
        feedback = get_object_or_404(DentistFeedback, id=feedback_id)
        data = json.loads(request.body)
        
        if 'comment_text' not in data:
            return JsonResponse({
                'success': False,
                'error': 'comment_text is required'
            }, status=400)
        
        comment = FeedbackComment.objects.create(
            feedback=feedback,
            author=request.user,
            comment_text=data['comment_text'],
            parent_comment_id=data.get('parent_comment_id')
        )
        
        return JsonResponse({
            'success': True,
            'comment_id': comment.id,
            'message': 'Comment added successfully'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def pending_validations(request):
    """
    Get list of diagnoses pending validation
    """
    try:
        # Get completed diagnoses without validation or with pending status
        validated_ids = ValidationStatus.objects.exclude(
            validation_status='pending'
        ).values_list('diagnosis_id', flat=True)
        
        pending = DiagnosisResult.objects.filter(
            status='completed'
        ).exclude(
            id__in=validated_ids
        ).order_by('-uploaded_at')
        
        # Pagination
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        start = (page - 1) * per_page
        end = start + per_page
        
        total_count = pending.count()
        pending_list = pending[start:end]
        
        diagnoses = []
        for diagnosis in pending_list:
            diagnoses.append({
                'id': diagnosis.id,
                'image_url': diagnosis.image.url,
                'uploaded_at': diagnosis.uploaded_at.isoformat(),
                'severity': diagnosis.severity,
                'confidence': diagnosis.confidence_score,
                'has_caries': diagnosis.has_caries,
                'num_lesions': len(diagnosis.lesion_boxes) if diagnosis.lesion_boxes else 0
            })
        
        return JsonResponse({
            'success': True,
            'pending_count': total_count,
            'page': page,
            'per_page': per_page,
            'total_pages': (total_count + per_page - 1) // per_page,
            'diagnoses': diagnoses
        })
        
    except Exception as e:
        print(f"Error in pending_validations: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def feedback_statistics(request):
    """
    Get aggregate statistics on feedback and AI performance
    """
    try:
        total_feedback = DentistFeedback.objects.count()
        total_diagnoses = DiagnosisResult.objects.filter(status='completed').count()
        
        if total_feedback == 0:
            return JsonResponse({
                'success': True,
                'statistics': {
                    'total_diagnoses': total_diagnoses,
                    'total_feedback': 0,
                    'message': 'No feedback data available yet'
                }
            })
        
        # Validation status breakdown
        validation_stats = ValidationStatus.objects.values('validation_status').annotate(
            count=Count('diagnosis')
        )
        
        # AI accuracy
        correct_predictions = DentistFeedback.objects.filter(is_correct=True).count()
        accuracy = (correct_predictions / total_feedback * 100)
        
        # Average rating
        avg_rating = DentistFeedback.objects.aggregate(
            avg_rating=Avg('ai_performance_rating')
        )['avg_rating'] or 0
        
        # Category breakdown
        category_stats = FeedbackCategory.objects.values('category').annotate(
            count=Count('id')
        )
        
        # Severity-specific accuracy
        severity_accuracy = {}
        for severity in ['Normal', 'Mild', 'Moderate', 'Severe']:
            severity_correct = DentistFeedback.objects.filter(
                diagnosis__severity=severity,
                is_correct=True
            ).count()
            
            severity_total = DentistFeedback.objects.filter(
                diagnosis__severity=severity
            ).count()
            
            if severity_total > 0:
                severity_accuracy[severity] = {
                    'accuracy': round((severity_correct / severity_total * 100), 2),
                    'total_cases': severity_total,
                    'correct_cases': severity_correct
                }
        
        # Recent feedback trends (last 30 days)
        from datetime import timedelta
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_feedback = DentistFeedback.objects.filter(
            created_at__gte=thirty_days_ago
        )
        recent_correct = recent_feedback.filter(is_correct=True).count()
        recent_total = recent_feedback.count()
        recent_accuracy = (recent_correct / recent_total * 100) if recent_total > 0 else 0
        
        return JsonResponse({
            'success': True,
            'statistics': {
                'total_diagnoses': total_diagnoses,
                'total_feedback': total_feedback,
                'feedback_coverage': round((total_feedback / total_diagnoses * 100), 2) if total_diagnoses > 0 else 0,
                'overall_accuracy': round(accuracy, 2),
                'average_rating': round(avg_rating, 2),
                'validation_status': list(validation_stats),
                'category_breakdown': list(category_stats),
                'severity_accuracy': severity_accuracy,
                'recent_trends': {
                    'last_30_days_feedback': recent_total,
                    'last_30_days_accuracy': round(recent_accuracy, 2)
                }
            }
        })
        
    except Exception as e:
        print(f"Error in feedback_statistics: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def dentist_dashboard(request):
    """
    Personalized dashboard for dentist
    """
    try:
        if not request.user.is_authenticated:
            return JsonResponse({
                'success': False,
                'error': 'Authentication required'
            }, status=401)
        
        # Dentist's feedback history
        my_feedback = DentistFeedback.objects.filter(
            dentist=request.user
        ).order_by('-created_at')[:10]
        
        # Validations by this dentist
        validated_by_me = ValidationStatus.objects.filter(
            validated_by=request.user
        ).count()
        
        # My accuracy contribution
        my_correct = DentistFeedback.objects.filter(
            dentist=request.user,
            is_correct=True
        ).count()
        my_total = DentistFeedback.objects.filter(dentist=request.user).count()
        
        feedback_list = []
        for feedback in my_feedback:
            feedback_list.append({
                'id': feedback.id,
                'diagnosis_id': feedback.diagnosis.id,
                'is_correct': feedback.is_correct,
                'severity': feedback.diagnosis.severity,
                'corrected_severity': feedback.corrected_severity,
                'rating': feedback.ai_performance_rating,
                'created_at': feedback.created_at.isoformat()
            })
        
        return JsonResponse({
            'success': True,
            'dentist': request.user.username,
            'statistics': {
                'total_validations': validated_by_me,
                'total_feedback': my_total,
                'cases_marked_correct': my_correct,
                'cases_marked_incorrect': my_total - my_correct
            },
            'recent_feedback': feedback_list
        })
        
    except Exception as e:
        print(f"Error in dentist_dashboard: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)