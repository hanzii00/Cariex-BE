import tensorflow as tf
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
            model_path = Path(__file__).parent / 'ml_models' / 'adult_teeth.h5'
            self._model = tf.keras.models.load_model(model_path)
            print(f"Model loaded from {model_path}")
        return self._model
    
    def preprocess_image(self, image_array, target_size=(224, 224)):
        """F5: Preprocessing Engine"""
        # Resize image
        img_resized = cv2.resize(image_array, target_size)
        
        # Normalize pixel values
        img_normalized = img_resized / 255.0
        
        # Add batch dimension
        img_batch = np.expand_dims(img_normalized, axis=0)
        
        return img_batch
    
    def predict(self, preprocessed_image):
        """F6: Caries Detection AI"""
        model = self.load_model()
        predictions = model.predict(preprocessed_image)
        return predictions
    
    def classify_severity(self, predictions):
        """F6: Severity Classification AI"""
        # Adjust based on your model's output format
        severity_labels = ['Normal', 'Mild', 'Moderate', 'Severe']
        severity_index = np.argmax(predictions)
        confidence = float(predictions[0][severity_index])
        
        return {
            'severity': severity_labels[severity_index],
            'confidence': confidence,
            'all_probabilities': predictions[0].tolist()
        }

# Singleton instance
model_loader = ModelLoader()