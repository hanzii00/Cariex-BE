try:
    import tensorflow as tf
except ImportError:
    tf = None
import numpy as np
from pathlib import Path
import cv2


class ModelLoader:
    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load_model(self):
        if self._model is None:
            if tf is None:
                raise ImportError(
                    "TensorFlow is not installed. Install tensorflow to use the AIModel features."
                )
            model_path = Path(__file__).parent / 'ml_models' / 'adult_teeth.h5'
            if not model_path.exists():
                raise FileNotFoundError(f"Model file not found at {model_path}")

            self._model = tf.keras.models.load_model(str(model_path), compile=False)
        return self._model

    def preprocess_image(self, image_array, target_size=None):
        model = self.load_model()
        if target_size is None:
            input_shape = model.input_shape[1:3]
            target_size = tuple(input_shape)

        img_resized = cv2.resize(image_array, target_size)
        img_normalized = img_resized.astype(np.float32) / 255.0
        img_batch = np.expand_dims(img_normalized, axis=0)
        return img_batch

    def predict(self, preprocessed_image):
        model = self.load_model()
        return model.predict(preprocessed_image, verbose=0)

    def classify_severity(self, predictions):
        predictions = np.array(predictions)

        if len(predictions.shape) == 4:
            segmentation_mask = predictions[0, :, :, 0]
            threshold = 0.5
            affected_pixels = np.sum(segmentation_mask > threshold)
            total_pixels = segmentation_mask.size
            affected_percentage = (affected_pixels / total_pixels) * 100
            mean_probability = segmentation_mask.mean()
            max_probability = segmentation_mask.max()

            if affected_percentage < 1:
                severity, confidence = 'Normal', (1 - mean_probability) * 100
            elif affected_percentage < 5:
                severity, confidence = 'Mild', mean_probability * 100
            elif affected_percentage < 15:
                severity, confidence = 'Moderate', mean_probability * 100
            else:
                severity, confidence = 'Severe', mean_probability * 100

            return {
                'severity': severity,
                'confidence': min(confidence, 100.0),
                'affected_percentage': affected_percentage,
                'mean_probability': float(mean_probability),
                'max_probability': float(max_probability),
                'segmentation_mask': segmentation_mask
            }

        elif len(predictions.shape) == 2:
            pred = predictions[0]
            severity_labels = ['Normal', 'Mild', 'Moderate', 'Severe']
            num_classes = pred.shape[0]
            if num_classes < len(severity_labels):
                severity_labels = severity_labels[:num_classes]

            severity_index = int(np.argmax(pred))
            confidence = float(pred[severity_index]) * 100

            return {
                'severity': severity_labels[severity_index],
                'confidence': confidence,
                'all_probabilities': [float(p) * 100 for p in pred]
            }

        return {
            'severity': 'Unknown',
            'confidence': 0.0,
            'error': f'Unexpected prediction shape: {predictions.shape}'
        }

    def generate_bounding_boxes(self, segmentation_mask, threshold=0.5, min_area=100):
        binary_mask = (segmentation_mask > threshold).astype(np.uint8) * 255
        contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        bounding_boxes = []
        for i, contour in enumerate(contours):
            area = cv2.contourArea(contour)
            if area > min_area:
                x, y, w, h = cv2.boundingRect(contour)
                roi = segmentation_mask[y:y+h, x:x+w]
                confidence = float(roi.mean()) * 100
                bounding_boxes.append({
                    'id': i + 1,
                    'x': int(x),
                    'y': int(y),
                    'width': int(w),
                    'height': int(h),
                    'confidence': round(confidence, 2),
                    'area': int(area)
                })
        return bounding_boxes


model_loader = ModelLoader()
