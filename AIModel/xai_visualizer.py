import tensorflow as tf
import numpy as np
import cv2
import matplotlib.pyplot as plt
from pathlib import Path

class XAIVisualizer:
    
    def __init__(self, model):
        self.model = model
        
    def generate_gradcam(self, image, layer_name=None):

        if layer_name is None:
            layer_name = self._find_last_conv_layer()
        
        grad_model = tf.keras.models.Model(
            inputs=[self.model.inputs],
            outputs=[self.model.get_layer(layer_name).output, self.model.output]
        )
        
        with tf.GradientTape() as tape:
            conv_outputs, predictions = grad_model(image)
            loss = tf.reduce_mean(predictions)
        
        grads = tape.gradient(loss, conv_outputs)
        
        pooled_grads = tf.reduce_mean(grads, axis=(0, 1, 2))
        
        conv_outputs = conv_outputs[0]
        heatmap = conv_outputs @ pooled_grads[..., tf.newaxis]
        heatmap = tf.squeeze(heatmap)
        
        heatmap = tf.maximum(heatmap, 0) / tf.math.reduce_max(heatmap)
        
        return heatmap.numpy()
    
    def _find_last_conv_layer(self):
        """Find the last convolutional layer in the model"""
        for layer in reversed(self.model.layers):
            if 'conv' in layer.name.lower():
                return layer.name
        return self.model.layers[-2].name  # Fallback
    
    def overlay_heatmap(self, heatmap, original_image, alpha=0.4, colormap=cv2.COLORMAP_JET):
        """
        Overlay heatmap on original image
        """
        heatmap_resized = cv2.resize(heatmap, (original_image.shape[1], original_image.shape[0]))
        
        heatmap_colored = cv2.applyColorMap(np.uint8(255 * heatmap_resized), colormap)
        heatmap_colored = cv2.cvtColor(heatmap_colored, cv2.COLOR_BGR2RGB)
        
        if original_image.dtype != np.uint8:
            original_image = (original_image * 255).astype(np.uint8)
        
        overlayed = cv2.addWeighted(original_image, 1-alpha, heatmap_colored, alpha, 0)
        
        return overlayed
    
    def generate_integrated_gradients(self, image, baseline=None, steps=50):
        """
        Integrated Gradients - more accurate attribution method
        Shows cumulative gradients along path from baseline to input
        """
        if baseline is None:
            baseline = np.zeros_like(image)
        
        # Generate interpolated images
        alphas = np.linspace(0, 1, steps)
        interpolated_images = []
        
        for alpha in alphas:
            interpolated = baseline + alpha * (image - baseline)
            interpolated_images.append(interpolated)
        
        interpolated_images = np.array(interpolated_images)
        
        # Calculate gradients
        with tf.GradientTape() as tape:
            inputs = tf.Variable(interpolated_images, dtype=tf.float32)
            tape.watch(inputs)
            predictions = self.model(inputs)
            loss = tf.reduce_mean(predictions, axis=[1, 2, 3])
        
        grads = tape.gradient(loss, inputs)
        
        # Average gradients
        avg_grads = tf.reduce_mean(grads, axis=0)
        
        # Integrated gradients
        integrated_grads = (image - baseline) * avg_grads
        
        return integrated_grads[0].numpy()
    
    def visualize_segmentation_overlay(self, original_image, segmentation_mask, threshold=0.5):
        """
        Create colored overlay of segmentation results
        Red = High caries probability, Green = Low/None
        """
        if len(segmentation_mask.shape) == 4:
            segmentation_mask = segmentation_mask[0, :, :, 0]
        
        # Resize to match original
        mask_resized = cv2.resize(segmentation_mask, 
                                   (original_image.shape[1], original_image.shape[0]))
        
        # Create colored mask
        colored_mask = np.zeros((*mask_resized.shape, 3), dtype=np.uint8)
        
        # Red channel = caries probability
        colored_mask[:, :, 0] = (mask_resized * 255).astype(np.uint8)
        
        # Green channel = inverse (healthy)
        colored_mask[:, :, 1] = ((1 - mask_resized) * 255).astype(np.uint8)
        
        # Prepare original image
        if original_image.dtype != np.uint8:
            original_image = (original_image * 255).astype(np.uint8)
        
        # Blend
        alpha = 0.5
        overlayed = cv2.addWeighted(original_image, 1-alpha, colored_mask, alpha, 0)
        
        return overlayed, colored_mask
    
    def create_explanation_report(self, original_image, preprocessed_image, 
                                  segmentation_mask, severity_result):
        """
        Generate comprehensive XAI visualization
        Returns figure with multiple explanation views
        """
        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        fig.suptitle('Explainable AI - Dental Caries Detection', fontsize=16, fontweight='bold')
        
        # 1. Original Image
        axes[0, 0].imshow(original_image)
        axes[0, 0].set_title('Original X-ray')
        axes[0, 0].axis('off')
        
        # 2. Segmentation Mask
        if len(segmentation_mask.shape) == 4:
            mask_2d = segmentation_mask[0, :, :, 0]
        else:
            mask_2d = segmentation_mask
        axes[0, 1].imshow(mask_2d, cmap='hot')
        axes[0, 1].set_title('Probability Heatmap')
        axes[0, 1].axis('off')
        
        # 3. Colored Overlay
        overlay, colored_mask = self.visualize_segmentation_overlay(original_image, segmentation_mask)
        axes[0, 2].imshow(overlay)
        axes[0, 2].set_title('Caries Overlay (Red=Caries)')
        axes[0, 2].axis('off')
        
        # 4. Grad-CAM
        try:
            gradcam = self.generate_gradcam(preprocessed_image)
            gradcam_overlay = self.overlay_heatmap(gradcam, original_image)
            axes[1, 0].imshow(gradcam_overlay)
            axes[1, 0].set_title('Grad-CAM Focus Areas')
        except Exception as e:
            axes[1, 0].text(0.5, 0.5, f'Grad-CAM unavailable:\n{str(e)}', 
                           ha='center', va='center')
            axes[1, 0].set_title('Grad-CAM')
        axes[1, 0].axis('off')
        
        # 5. Threshold Visualization
        binary_mask = (mask_2d > 0.5).astype(np.uint8) * 255
        axes[1, 1].imshow(binary_mask, cmap='gray')
        axes[1, 1].set_title(f'Binary Detection (>50% confidence)')
        axes[1, 1].axis('off')
        
        # 6. Statistics
        stats_text = f"""
Severity: {severity_result.get('severity', 'N/A')}
Confidence: {severity_result.get('confidence', 0):.2f}%

Affected Area: {severity_result.get('affected_percentage', 0):.2f}%
Mean Probability: {severity_result.get('mean_probability', 0):.4f}
Max Probability: {severity_result.get('max_probability', 0):.4f}

Interpretation:
- Red areas: Suspected caries
- Brighter = Higher confidence
- Green areas: Healthy tissue
        """
        axes[1, 2].text(0.1, 0.5, stats_text, fontsize=10, 
                       verticalalignment='center', family='monospace')
        axes[1, 2].set_title('Detection Statistics')
        axes[1, 2].axis('off')
        
        plt.tight_layout()
        
        return fig
    
    def save_explanation(self, fig, output_path):
        """Save XAI visualization to file"""
        fig.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"✓ XAI explanation saved to {output_path}")


# Example usage in your Django views
def generate_xai_explanation(diagnosis_id):
    """
    Generate XAI visualization for a diagnosis
    No LLM needed - pure computer vision
    """
    from .models import DiagnosisResult
    from .model_loader import model_loader
    
    diagnosis = DiagnosisResult.objects.get(id=diagnosis_id)
    
    # Load original image
    image_path = diagnosis.image.path
    original_image = cv2.imread(image_path)
    original_image = cv2.cvtColor(original_image, cv2.COLOR_BGR2RGB)
    
    # Preprocess
    preprocessed = model_loader.preprocess_image(original_image)
    
    # Get predictions
    predictions = model_loader.predict(preprocessed)
    severity_result = model_loader.classify_severity(predictions)
    
    # Create XAI visualizer
    xai = XAIVisualizer(model_loader.load_model())
    
    # Generate explanation
    fig = xai.create_explanation_report(
        original_image=original_image,
        preprocessed_image=preprocessed,
        segmentation_mask=predictions,
        severity_result=severity_result
    )
    
    # Save
    output_dir = Path(diagnosis.image.path).parent
    output_path = output_dir / f'xai_explanation_{diagnosis_id}.png'
    xai.save_explanation(fig, output_path)
    
    return str(output_path)