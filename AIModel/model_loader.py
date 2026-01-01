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
        """Load the model without compilation to avoid loss function issues"""
        if self._model is None:
            model_path = Path(__file__).parent / 'ml_models' / 'adult_teeth.h5'
            
            # Check if file exists before loading
            if not model_path.exists():
                raise FileNotFoundError(f"Model file not found at {model_path}")
            
            # Load without compilation to avoid custom loss function errors
            self._model = tf.keras.models.load_model(
                str(model_path), 
                compile=False
            )
            print(f"✓ Model loaded successfully from {model_path}")
            print(f"  Input shape: {self._model.input_shape}")
            print(f"  Output shape: {self._model.output_shape}")
        return self._model
    
    def preprocess_image(self, image_array, target_size=None):
        """
        F5: Preprocessing Engine
        Adjust target_size based on your model's input requirements
        """
        model = self.load_model()
        
        # Get target size from model if not specified
        if target_size is None:
            input_shape = model.input_shape[1:3]  # Get height and width
            target_size = tuple(input_shape)
        
        # Resize image
        img_resized = cv2.resize(image_array, target_size)
        
        # Normalize pixel values (0-255 to 0-1)
        img_normalized = img_resized.astype(np.float32) / 255.0
        
        # Add batch dimension
        img_batch = np.expand_dims(img_normalized, axis=0)
        
        return img_batch
    
    def predict(self, preprocessed_image):
        """F6: Caries Detection AI"""
        model = self.load_model()
        predictions = model.predict(preprocessed_image, verbose=0)
        return predictions
    
    def classify_severity(self, predictions):
        """
        F6: Severity Classification AI
        Handles segmentation output (pixel-wise predictions)
        """
        # Convert to numpy array if not already
        predictions = np.array(predictions)
        
        print(f"DEBUG classify_severity - Shape: {predictions.shape}")
        
        # Handle segmentation output: (1, height, width, 1)
        if len(predictions.shape) == 4:
            # Remove batch and channel dimensions
            segmentation_mask = predictions[0, :, :, 0]
            
            print(f"DEBUG: Segmentation mask shape: {segmentation_mask.shape}")
            print(f"DEBUG: Min value: {segmentation_mask.min():.4f}, Max value: {segmentation_mask.max():.4f}")
            print(f"DEBUG: Mean value: {segmentation_mask.mean():.4f}")
            
            # Calculate percentage of pixels above threshold
            threshold = 0.5
            affected_pixels = np.sum(segmentation_mask > threshold)
            total_pixels = segmentation_mask.size
            affected_percentage = (affected_pixels / total_pixels) * 100
            
            # Calculate mean probability of affected areas
            mean_probability = segmentation_mask.mean()
            max_probability = segmentation_mask.max()
            
            print(f"DEBUG: Affected pixels: {affected_pixels}/{total_pixels} ({affected_percentage:.2f}%)")
            print(f"DEBUG: Mean probability: {mean_probability:.4f}")
            print(f"DEBUG: Max probability: {max_probability:.4f}")
            
            # Classify severity based on affected area and intensity
            if affected_percentage < 1:
                severity = 'Normal'
                confidence = (1 - mean_probability) * 100
            elif affected_percentage < 5:
                severity = 'Mild'
                confidence = mean_probability * 100
            elif affected_percentage < 15:
                severity = 'Moderate'
                confidence = mean_probability * 100
            else:
                severity = 'Severe'
                confidence = mean_probability * 100
            
            return {
                'severity': severity,
                'confidence': min(confidence, 100.0),
                'affected_percentage': affected_percentage,
                'mean_probability': float(mean_probability),
                'max_probability': float(max_probability),
                'segmentation_mask': segmentation_mask  # Include for bounding box generation
            }
        
        # Fallback for other output formats
        elif len(predictions.shape) == 2:
            # Standard classification output (1, num_classes)
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
        
        else:
            # Unknown format
            return {
                'severity': 'Unknown',
                'confidence': 0.0,
                'error': f'Unexpected prediction shape: {predictions.shape}'
            }
    
    def generate_bounding_boxes(self, segmentation_mask, threshold=0.5, min_area=100):
        """
        Generate bounding boxes from segmentation mask
        """
        # Threshold the mask
        binary_mask = (segmentation_mask > threshold).astype(np.uint8) * 255
        
        # Find contours
        contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        bounding_boxes = []
        for i, contour in enumerate(contours):
            area = cv2.contourArea(contour)
            if area > min_area:
                x, y, w, h = cv2.boundingRect(contour)
                
                # Calculate confidence for this region
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

# Singleton instance
model_loader = ModelLoader()