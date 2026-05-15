def _import_tensorflow():
    try:
        import tensorflow as tf
        return tf
    except ImportError:
        return None

import numpy as np
from pathlib import Path
import os
import urllib.request
from django.conf import settings  

try:
    import cv2
except ImportError:
    cv2 = None


class ModelLoader:
    _instance = None
    _model = None
    _grad_model = None
    _last_grad_layer = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def aws_model_url(self):
        url = getattr(settings, 'AWS_MODEL_URL', None)
        if not url:
            raise EnvironmentError(
                "AWS_MODEL_URL is not configured in Django settings."
            )
        return url

    def download_model_if_needed(self, model_path):
        if model_path.exists():
            print(f"Model already exists at {model_path}")
            return

        print(f"Downloading model from AWS S3...")
        try:
            model_path.parent.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(self.aws_model_url, str(model_path))
            print(f"Model downloaded successfully to {model_path}")
        except Exception as e:
            print(f"Error downloading model: {e}")
            if model_path.exists():
                model_path.unlink()
            raise

    def load_model(self):
        if self._model is None:
            tf = _import_tensorflow()
            if tf is None:
                raise ImportError(
                    "TensorFlow is not installed. Install tensorflow to use the AIModel features."
                )

            model_path = Path(__file__).parent / 'ml_models' / 'new_model.keras'
            self.download_model_if_needed(model_path)

            if not model_path.exists():
                raise FileNotFoundError(f"Model file not found at {model_path}")

            print(f"Loading model from {model_path}")
            self._model = tf.keras.models.load_model(str(model_path), compile=False)
            print("Model loaded successfully")

        return self._model

    def load_grad_model(self, layer_name):
        if self._grad_model is None or self._last_grad_layer != layer_name:
            tf = _import_tensorflow()
            model = self.load_model()
            print(f"Building grad model for layer: {layer_name}")
            self._grad_model = tf.keras.models.Model(
                inputs=[model.inputs],
                outputs=[model.get_layer(layer_name).output, model.output]
            )
            self._last_grad_layer = layer_name
            print("Grad model built and cached")
        return self._grad_model

    def preprocess_image(self, image_array, target_size=None):
        model = self.load_model()
        if target_size is None:
            input_shape = model.input_shape[1:3]
            target_size = tuple(input_shape)

        if cv2 is None:
            raise ImportError("OpenCV (cv2) is required.")

        img_resized = cv2.resize(image_array, target_size)
        img_batch = np.expand_dims(img_resized.astype(np.float32), axis=0)
        return img_batch

    def predict(self, preprocessed_image):
        model = self.load_model()
        return model.predict(preprocessed_image, verbose=0)

    def classify_severity(self, predictions):
        predictions = np.array(predictions)

        if len(predictions.shape) == 4:
            segmentation_mask = predictions[0, :, :, 0]
            max_prob = float(segmentation_mask.max())
            mean_prob = float(segmentation_mask.mean())
            adaptive_threshold = max(0.5 * max_prob, 0.05)
            affected_pixels = np.sum(segmentation_mask > adaptive_threshold)
            total_pixels = segmentation_mask.size
            affected_percentage = (affected_pixels / total_pixels) * 100

            if affected_percentage < 1:
                severity, confidence = 'Healthy', (1 - mean_prob) * 100
            elif affected_percentage < 5:
                severity, confidence = 'Moderate', mean_prob * 100
            else:
                severity, confidence = 'Deep', mean_prob * 100

            return {
                'severity': severity,
                'confidence': min(confidence, 100.0),
                'has_caries': severity.lower() != 'healthy',
                'affected_percentage': affected_percentage,
                'mean_probability': mean_prob,
                'max_probability': max_prob,
                'segmentation_mask': segmentation_mask,
            }

        elif len(predictions.shape) == 2:
            pred = predictions[0]
            severity_labels = ['Healthy', 'Moderate', 'Deep']
            num_classes = pred.shape[0]
            severity_labels = severity_labels[:num_classes]

            severity_index = int(np.argmax(pred))
            confidence = float(pred[severity_index]) * 100
            severity = severity_labels[severity_index]
            has_caries = severity.lower() != 'healthy'

            return {
                'severity': severity,
                'confidence': confidence,
                'has_caries': has_caries,
                'class_labels': severity_labels,
                'all_probabilities': [float(p) * 100 for p in pred],
                'affected_percentage': 0.0,
                'mean_probability': float(np.mean(pred)),
                'max_probability': float(np.max(pred)),
            }

        return {
            'severity': 'Unknown',
            'confidence': 0.0,
            'has_caries': False,
            'affected_percentage': 0.0,
            'mean_probability': 0.0,
            'max_probability': 0.0,
            'error': f'Unexpected prediction shape: {predictions.shape}',
        }

    def generate_bounding_boxes(self, segmentation_mask, threshold=0.5, min_area=100):
        if cv2 is None:
            raise ImportError("OpenCV (cv2) is required for bounding box generation.")

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