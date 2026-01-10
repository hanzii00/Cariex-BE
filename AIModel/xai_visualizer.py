import numpy as np
from pathlib import Path

# Import TensorFlow conditionally
try:
    import tensorflow as tf
    HAVE_TENSORFLOW = True
except ImportError:
    tf = None
    HAVE_TENSORFLOW = False

# Import OpenCV conditionally
try:
    import cv2
    HAVE_CV2 = True
except ImportError:
    cv2 = None
    HAVE_CV2 = False

# Import matplotlib conditionally
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    HAVE_MATPLOTLIB = True
except ImportError:
    matplotlib = None
    plt = None
    HAVE_MATPLOTLIB = False


class XAIVisualizer:
    def __init__(self, model):
        if not HAVE_TENSORFLOW:
            raise ImportError('TensorFlow is required for XAI visualization')
        if not HAVE_CV2:
            raise ImportError('OpenCV (cv2) is required for XAI visualization')
        self.model = model

    def generate_gradcam(self, image, layer_name=None):
        if not HAVE_TENSORFLOW:
            raise ImportError('TensorFlow is required for Grad-CAM')
        
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
        for layer in reversed(self.model.layers):
            if 'conv' in layer.name.lower():
                return layer.name
        return self.model.layers[-2].name

    def overlay_heatmap(self, heatmap, original_image, alpha=0.4, colormap=None):
        if not HAVE_CV2:
            raise ImportError('OpenCV (cv2) is required for heatmap overlay')
        
        if colormap is None:
            colormap = cv2.COLORMAP_JET
            
        heatmap_resized = cv2.resize(heatmap, (original_image.shape[1], original_image.shape[0]))
        heatmap_colored = cv2.applyColorMap(np.uint8(255 * heatmap_resized), colormap)
        heatmap_colored = cv2.cvtColor(heatmap_colored, cv2.COLOR_BGR2RGB)

        if original_image.dtype != np.uint8:
            original_image = (original_image * 255).astype(np.uint8)

        overlayed = cv2.addWeighted(original_image, 1 - alpha, heatmap_colored, alpha, 0)
        return overlayed

    def generate_integrated_gradients(self, image, baseline=None, steps=50):
        if not HAVE_TENSORFLOW:
            raise ImportError('TensorFlow is required for Integrated Gradients')
            
        if baseline is None:
            baseline = np.zeros_like(image)

        alphas = np.linspace(0, 1, steps)
        interpolated_images = np.array([baseline + alpha * (image - baseline) for alpha in alphas])

        with tf.GradientTape() as tape:
            inputs = tf.Variable(interpolated_images, dtype=tf.float32)
            tape.watch(inputs)
            predictions = self.model(inputs)
            loss = tf.reduce_mean(predictions, axis=[1, 2, 3])

        grads = tape.gradient(loss, inputs)
        avg_grads = tf.reduce_mean(grads, axis=0)
        integrated_grads = (image - baseline) * avg_grads
        return integrated_grads[0].numpy()

    def visualize_segmentation_overlay(self, original_image, segmentation_mask, threshold=0.5):
        if not HAVE_CV2:
            raise ImportError('OpenCV (cv2) is required for segmentation overlay')
            
        if len(segmentation_mask.shape) == 4:
            segmentation_mask = segmentation_mask[0, :, :, 0]

        mask_resized = cv2.resize(segmentation_mask, (original_image.shape[1], original_image.shape[0]))

        if original_image.dtype != np.uint8:
            original_image_uint8 = (original_image * 255).astype(np.uint8)
        else:
            original_image_uint8 = original_image.copy()

        max_prob = np.max(mask_resized)
        mean_prob = np.mean(mask_resized)
        has_detection = (max_prob > 0.6) and (mean_prob > 0.01)

        if not has_detection:
            colored_mask = np.zeros((*mask_resized.shape, 3), dtype=np.uint8)
            return original_image_uint8, colored_mask

        colored_mask = np.zeros((*mask_resized.shape, 3), dtype=np.uint8)
        caries_regions = mask_resized > threshold
        colored_mask[:, :, 0] = np.where(caries_regions, (mask_resized * 255).astype(np.uint8), 0)

        warning_regions = (mask_resized > 0.1) & (mask_resized <= threshold)
        colored_mask[:, :, 0] = np.where(warning_regions, (mask_resized * 200).astype(np.uint8), colored_mask[:, :, 0])
        colored_mask[:, :, 1] = np.where(warning_regions, (mask_resized * 200).astype(np.uint8), 0)

        alpha = 0.6
        overlayed = cv2.addWeighted(original_image_uint8, 1 - alpha, colored_mask, alpha, 0)
        return overlayed, colored_mask

    def create_explanation_report(self, original_image, preprocessed_image, segmentation_mask, severity_result):
        if not HAVE_MATPLOTLIB or plt is None:
            raise ImportError('matplotlib is required to create XAI explanation reports')

        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        fig.suptitle('Explainable AI - Dental Caries Detection', fontsize=16, fontweight='bold')

        affected_pct = severity_result.get('affected_percentage', 0)
        mean_prob = severity_result.get('mean_probability', 0)
        max_prob = severity_result.get('max_probability', 0)
        severity = severity_result.get('severity', 'N/A')
        confidence = severity_result.get('confidence', 0)
        has_caries = (affected_pct > 0.5) and (max_prob > 0.6)

        axes[0, 0].imshow(original_image)
        axes[0, 0].set_title('Original X-ray')
        axes[0, 0].axis('off')

        if len(segmentation_mask.shape) == 4:
            mask_2d = segmentation_mask[0, :, :, 0]
        else:
            mask_2d = segmentation_mask
        axes[0, 1].imshow(mask_2d, cmap='hot')
        axes[0, 1].set_title('Probability Heatmap')
        axes[0, 1].axis('off')

        overlay, _ = self.visualize_segmentation_overlay(original_image, segmentation_mask)
        axes[0, 2].imshow(overlay)
        axes[0, 2].set_title('Caries Detection (Red=Detected)' if has_caries else 'No Caries Detected')
        axes[0, 2].axis('off')

        try:
            gradcam = self.generate_gradcam(preprocessed_image)
            gradcam_overlay = self.overlay_heatmap(gradcam, original_image)
            axes[1, 0].imshow(gradcam_overlay)
            axes[1, 0].set_title('Grad-CAM Focus Areas')
        except Exception as e:
            axes[1, 0].text(0.5, 0.5, f'Grad-CAM unavailable:\n{str(e)}', ha='center', va='center', fontsize=9)
            axes[1, 0].set_title('Grad-CAM')
        axes[1, 0].axis('off')

        binary_mask = (mask_2d > 0.5).astype(np.uint8) * 255
        axes[1, 1].imshow(binary_mask, cmap='gray')
        axes[1, 1].set_title('Binary Detection (>50% confidence)')
        axes[1, 1].axis('off')

        if has_caries:
            interpretation = """Interpretation:
- Red areas: Suspected caries
- Brighter = Higher confidence
- Green areas: Healthy tissue
- Review red regions clinically"""
        else:
            interpretation = """Interpretation:
- No caries detected
- All regions below threshold
- Image shows healthy tissue
- Routine monitoring recommended"""

        stats_text = f"""Severity: {severity}
Confidence: {confidence:.2f}%

Affected Area: {affected_pct:.2f}%
Mean Probability: {mean_prob:.4f}
Max Probability: {max_prob:.4f}

{interpretation}
"""
        axes[1, 2].text(0.1, 0.5, stats_text, fontsize=10, verticalalignment='center', family='monospace')
        axes[1, 2].set_title('Detection Statistics')
        axes[1, 2].axis('off')

        plt.tight_layout()
        return fig

    def save_explanation(self, fig, output_path):
        if not HAVE_MATPLOTLIB or plt is None:
            raise ImportError('matplotlib is required to save XAI explanation reports')
        fig.savefig(output_path, dpi=150, bbox_inches='tight')


def generate_xai_explanation(diagnosis_id):
    """Legacy function - requires all dependencies"""
    if not HAVE_CV2:
        raise ImportError('OpenCV (cv2) is required for XAI explanation generation')
    if not HAVE_TENSORFLOW:
        raise ImportError('TensorFlow is required for XAI explanation generation')
        
    from .models import DiagnosisResult
    from .model_loader import model_loader

    diagnosis = DiagnosisResult.objects.get(id=diagnosis_id)
    image_path = diagnosis.image.path
    original_image = cv2.imread(image_path)
    original_image = cv2.cvtColor(original_image, cv2.COLOR_BGR2RGB)

    preprocessed = model_loader.preprocess_image(original_image)
    predictions = model_loader.predict(preprocessed)
    severity_result = model_loader.classify_severity(predictions)

    xai = XAIVisualizer(model_loader.load_model())
    fig = xai.create_explanation_report(
        original_image=original_image,
        preprocessed_image=preprocessed,
        segmentation_mask=predictions,
        severity_result=severity_result
    )

    output_dir = Path(diagnosis.image.path).parent
    output_path = output_dir / f'xai_explanation_{diagnosis_id}.png'
    xai.save_explanation(fig, output_path)

    return str(output_path)