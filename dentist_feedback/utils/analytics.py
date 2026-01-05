from django.db.models import Avg, Count, Q
from ..models import DentistFeedback, FeedbackCategory, ModelPerformanceMetric

class FeedbackAnalyzer:
    @staticmethod
    def calculate_metrics():
        """Calculate comprehensive performance metrics"""
        total_feedback = DentistFeedback.objects.count()
        if total_feedback == 0:
            return {'error': 'No feedback data'}
        
        correct = DentistFeedback.objects.filter(is_correct=True).count()
        accuracy = (correct / total_feedback) * 100
        
        # Calculate precision, recall, F1
        true_positives = DentistFeedback.objects.filter(
            diagnosis__has_caries=True,
            is_correct=True
        ).count()
        
        false_positives = FeedbackCategory.objects.filter(
            category='false_positive'
        ).count()
        
        false_negatives = FeedbackCategory.objects.filter(
            category='false_negative'
        ).count()
        
        precision = (true_positives / (true_positives + false_positives) * 100) \
            if (true_positives + false_positives) > 0 else 0
        
        recall = (true_positives / (true_positives + false_negatives) * 100) \
            if (true_positives + false_negatives) > 0 else 0
        
        f1 = (2 * precision * recall / (precision + recall)) \
            if (precision + recall) > 0 else 0
        
        return {
            'accuracy': round(accuracy, 2),
            'precision': round(precision, 2),
            'recall': round(recall, 2),
            'f1_score': round(f1, 2),
            'total_feedback': total_feedback
        }