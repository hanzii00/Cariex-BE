import numpy as np
from pathlib import Path

try:
    import tensorflow as tf
    HAVE_TENSORFLOW = True
except ImportError:
    tf = None
    HAVE_TENSORFLOW = False

try:
    import cv2
    HAVE_CV2 = True
except ImportError:
    cv2 = None
    HAVE_CV2 = False

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

    # ── Model type detection ──────────────────────────────────────────────────

    def _is_segmentation_model(self, predictions):
        """True if predictions are a spatial mask (4-D), False if classification (2-D)."""
        return len(np.array(predictions).shape) == 4

    def _adaptive_threshold(self, mask):
        """Scale threshold to the model's actual output range."""
        max_prob = float(np.max(mask))
        return max(0.5 * max_prob, 0.05)

    # ── Grad-CAM ──────────────────────────────────────────────────────────────

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

            # Handle classification (2-D) vs segmentation (4-D) output
            if len(predictions.shape) == 2:
                # Classification: use the highest-confidence class score as loss
                loss = predictions[0, tf.argmax(predictions[0])]
            else:
                # Segmentation: use mean of all predictions
                loss = tf.reduce_mean(predictions)

        grads = tape.gradient(loss, conv_outputs)

        # Pool gradients across spatial dims if they exist
        if len(grads.shape) == 4:
            pooled_grads = tf.reduce_mean(grads, axis=(0, 1, 2))
        elif len(grads.shape) == 3:
            pooled_grads = tf.reduce_mean(grads, axis=(0, 1))
        else:
            pooled_grads = tf.reduce_mean(grads, axis=0)

        conv_outputs = conv_outputs[0]

        # Build heatmap — handle both 3-D (H,W,C) and 2-D (H,C) conv outputs
        if len(conv_outputs.shape) == 3:
            heatmap = conv_outputs @ pooled_grads[..., tf.newaxis]
            heatmap = tf.squeeze(heatmap)
        else:
            heatmap = tf.reduce_mean(conv_outputs * pooled_grads, axis=-1)

        heatmap = tf.maximum(heatmap, 0)
        max_val = tf.math.reduce_max(heatmap)
        if max_val > 0:
            heatmap = heatmap / max_val

        # Ensure 2-D output
        heatmap_np = heatmap.numpy()
        if heatmap_np.ndim == 0:
            heatmap_np = np.ones((8, 8), dtype=np.float32) * float(heatmap_np)
        elif heatmap_np.ndim == 1:
            size = max(int(np.sqrt(len(heatmap_np))), 1)
            heatmap_np = heatmap_np[:size * size].reshape(size, size)

        return heatmap_np

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

        heatmap_resized = cv2.resize(
            heatmap.astype(np.float32),
            (original_image.shape[1], original_image.shape[0])
        )
        heatmap_colored = cv2.applyColorMap(np.uint8(255 * heatmap_resized), colormap)
        heatmap_colored = cv2.cvtColor(heatmap_colored, cv2.COLOR_BGR2RGB)

        if original_image.dtype != np.uint8:
            original_image = (original_image * 255).astype(np.uint8)

        return cv2.addWeighted(original_image, 1 - alpha, heatmap_colored, alpha, 0)

    # ── Segmentation overlay ──────────────────────────────────────────────────

    def visualize_segmentation_overlay(self, original_image, segmentation_mask, threshold=None):
        if not HAVE_CV2:
            raise ImportError('OpenCV (cv2) is required for segmentation overlay')

        if len(segmentation_mask.shape) == 4:
            segmentation_mask = segmentation_mask[0, :, :, 0]

        mask_resized = cv2.resize(
            segmentation_mask.astype(np.float32),
            (original_image.shape[1], original_image.shape[0])
        )

        if original_image.dtype != np.uint8:
            original_image_uint8 = (original_image * 255).astype(np.uint8)
        else:
            original_image_uint8 = original_image.copy()

        if threshold is None:
            threshold = self._adaptive_threshold(mask_resized)

        max_prob  = float(np.max(mask_resized))
        mean_prob = float(np.mean(mask_resized))

        has_detection = max_prob > (threshold * 0.5) and mean_prob > 0.005

        colored_mask = np.zeros((*mask_resized.shape, 3), dtype=np.uint8)

        if has_detection:
            caries_regions = mask_resized > threshold
            colored_mask[:, :, 0] = np.where(
                caries_regions, (mask_resized * 255).astype(np.uint8), 0)

            warning_regions = (mask_resized > threshold * 0.3) & (mask_resized <= threshold)
            colored_mask[:, :, 0] = np.where(
                warning_regions,
                (mask_resized * 200).astype(np.uint8),
                colored_mask[:, :, 0],
            )
            colored_mask[:, :, 1] = np.where(
                warning_regions, (mask_resized * 200).astype(np.uint8), 0)

        overlayed = cv2.addWeighted(original_image_uint8, 0.4, colored_mask, 0.6, 0)
        return overlayed, colored_mask

    # ── Full report ───────────────────────────────────────────────────────────

    def create_explanation_report(self, original_image, preprocessed_image,
                                  segmentation_mask, severity_result):
        if not HAVE_MATPLOTLIB or plt is None:
            raise ImportError('matplotlib is required to create XAI explanation reports')

        is_segmentation = self._is_segmentation_model(segmentation_mask)

        severity   = severity_result.get('severity', 'N/A')
        confidence = float(severity_result.get('confidence', 0))

        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        fig.suptitle('Explainable AI - Dental Caries Detection',
                     fontsize=16, fontweight='bold')

        # ── [0,0] Original ────────────────────────────────────────────────────
        axes[0, 0].imshow(original_image)
        axes[0, 0].set_title('Original Peri-apical X-ray')
        axes[0, 0].axis('off')

        # ── [0,1] Probability heatmap ─────────────────────────────────────────
        if is_segmentation:
            mask_2d = segmentation_mask[0, :, :, 0]
            axes[0, 1].imshow(mask_2d, cmap='hot')
            axes[0, 1].set_title('Probability Heatmap')
        else:
            # Classification model — show a confidence bar chart instead
            probs      = severity_result.get('all_probabilities', [confidence])
            labels     = ['Normal', 'Mild', 'Moderate', 'Severe'][:len(probs)]
            colors     = ['#2ecc71', '#f1c40f', '#e67e22', '#e74c3c'][:len(probs)]
            axes[0, 1].barh(labels, probs, color=colors)
            axes[0, 1].set_xlim(0, 100)
            axes[0, 1].set_xlabel('Confidence (%)')
            axes[0, 1].set_title('Class Probabilities')
            for i, v in enumerate(probs):
                axes[0, 1].text(v + 1, i, f'{v:.1f}%', va='center', fontsize=9)
        axes[0, 1].axis('off') if is_segmentation else None

        # ── [0,2] Overlay / severity badge ────────────────────────────────────
        if is_segmentation:
            mask_2d            = segmentation_mask[0, :, :, 0]
            adaptive_threshold = self._adaptive_threshold(mask_2d)
            affected_pixels    = float(np.sum(mask_2d > adaptive_threshold) / mask_2d.size * 100)
            has_caries         = affected_pixels > 1.0 or float(np.max(mask_2d)) > 0.15
            overlay, _         = self.visualize_segmentation_overlay(
                original_image, segmentation_mask, threshold=adaptive_threshold)
            axes[0, 2].imshow(overlay)
            axes[0, 2].set_title(
                'Caries Detection (Red=Detected)' if has_caries else 'No Caries Detected')
        else:
            # Show original image tinted by severity
            severity_colors = {
                'Normal':   (0.18, 0.80, 0.44),
                'Mild':     (0.95, 0.77, 0.06),
                'Moderate': (0.90, 0.49, 0.13),
                'Severe':   (0.91, 0.30, 0.24),
            }
            color           = severity_colors.get(severity, (0.5, 0.5, 0.5))
            tint            = np.full_like(original_image, [int(c * 255) for c in color], dtype=np.uint8)
            img_uint8       = original_image if original_image.dtype == np.uint8 else (original_image * 255).astype(np.uint8)
            tinted          = cv2.addWeighted(img_uint8, 0.8, tint, 0.2, 0)
            has_caries      = severity.lower() not in ['normal']
            axes[0, 2].imshow(tinted)
            axes[0, 2].set_title(f'Severity: {severity}')
            affected_pixels = 0.0
            adaptive_threshold = 0.5
        axes[0, 2].axis('off')

        # ── [1,0] Grad-CAM ────────────────────────────────────────────────────
        try:
            gradcam         = self.generate_gradcam(preprocessed_image)
            gradcam_overlay = self.overlay_heatmap(gradcam, original_image)
            axes[1, 0].imshow(gradcam_overlay)
            axes[1, 0].set_title('Grad-CAM Focus Areas')
        except Exception as e:
            axes[1, 0].text(0.5, 0.5, f'Grad-CAM unavailable:\n{str(e)}',
                            ha='center', va='center', fontsize=8, wrap=True)
            axes[1, 0].set_title('Grad-CAM')
        axes[1, 0].axis('off')

        # ── [1,1] Binary mask / confidence dial ───────────────────────────────
        if is_segmentation:
            mask_2d     = segmentation_mask[0, :, :, 0]
            binary_mask = (mask_2d > adaptive_threshold).astype(np.uint8) * 255
            axes[1, 1].imshow(binary_mask, cmap='gray')
            axes[1, 1].set_title(f'Binary Detection (threshold={adaptive_threshold:.2f})')
        else:
            # Show a simple confidence gauge
            theta  = np.linspace(0, np.pi, 200)
            axes[1, 1].plot(np.cos(theta), np.sin(theta), 'lightgray', lw=8)
            angle  = np.pi * (1 - confidence / 100)
            axes[1, 1].annotate('', xy=(np.cos(angle) * 0.8, np.sin(angle) * 0.8),
                                 xytext=(0, 0),
                                 arrowprops=dict(arrowstyle='->', color='crimson', lw=3))
            axes[1, 1].text(0, -0.3, f'{confidence:.1f}%', ha='center',
                            fontsize=16, fontweight='bold')
            axes[1, 1].text(0, -0.55, 'Confidence', ha='center', fontsize=10)
            axes[1, 1].set_xlim(-1.2, 1.2)
            axes[1, 1].set_ylim(-0.7, 1.2)
            axes[1, 1].set_title('Model Confidence')
        axes[1, 1].axis('off')

        # ── [1,2] Stats ───────────────────────────────────────────────────────
        affected_pct = float(severity_result.get('affected_percentage', affected_pixels))
        mean_prob    = float(severity_result.get('mean_probability', 0))
        max_prob     = float(severity_result.get('max_probability', 0))

        if has_caries:
            interpretation = (
                "Interpretation:\n"
                "- Caries regions highlighted\n"
                "- Brighter = Higher confidence\n"
                "- Orange areas: Borderline regions\n"
                "- Review red regions clinically"
            )
        else:
            interpretation = (
                "Interpretation:\n"
                "- No caries detected\n"
                "- All regions below threshold\n"
                "- Image shows healthy tissue\n"
                "- Routine monitoring recommended"
            )

        if is_segmentation:
            stats_text = (
                f"Severity: {severity}\n"
                f"Confidence: {confidence:.2f}%\n\n"
                f"Threshold (adaptive): {adaptive_threshold:.3f}\n"
                f"Affected Area: {affected_pixels:.2f}%\n"
                f"Mean Probability: {mean_prob:.4f}\n"
                f"Max Probability:  {max_prob:.4f}\n\n"
                f"{interpretation}\n"
            )
        else:
            probs      = severity_result.get('all_probabilities', [])
            labels     = ['Normal', 'Mild', 'Moderate', 'Severe']
            prob_lines = '\n'.join(
                f"  {labels[i]}: {p:.1f}%" for i, p in enumerate(probs)
            ) if probs else ''
            stats_text = (
                f"Severity: {severity}\n"
                f"Confidence: {confidence:.2f}%\n\n"
                f"Class Probabilities:\n{prob_lines}\n\n"
                f"{interpretation}\n"
            )

        axes[1, 2].text(0.05, 0.95, stats_text, fontsize=9.5,
                        verticalalignment='top', family='monospace',
                        transform=axes[1, 2].transAxes, linespacing=1.5)
        axes[1, 2].set_title('Detection Statistics')
        axes[1, 2].axis('off')

        plt.tight_layout()
        return fig

    def save_explanation(self, fig, output_path):
        if not HAVE_MATPLOTLIB or plt is None:
            raise ImportError('matplotlib is required to save XAI explanation reports')
        fig.savefig(output_path, dpi=150, bbox_inches='tight')


def generate_xai_explanation(diagnosis_id):
    """Legacy helper."""
    if not HAVE_CV2:
        raise ImportError('OpenCV (cv2) is required for XAI explanation generation')
    if not HAVE_TENSORFLOW:
        raise ImportError('TensorFlow is required for XAI explanation generation')

    from .models import DiagnosisResult
    from .model_loader import model_loader

    diagnosis      = DiagnosisResult.objects.get(id=diagnosis_id)
    image_path     = diagnosis.image.path
    original_image = cv2.imread(image_path)
    original_image = cv2.cvtColor(original_image, cv2.COLOR_BGR2RGB)

    preprocessed    = model_loader.preprocess_image(original_image)
    predictions     = model_loader.predict(preprocessed)
    severity_result = model_loader.classify_severity(predictions)

    xai = XAIVisualizer(model_loader.load_model())
    fig = xai.create_explanation_report(
        original_image=original_image,
        preprocessed_image=preprocessed,
        segmentation_mask=predictions,
        severity_result=severity_result,
    )

    output_dir  = Path(diagnosis.image.path).parent
    output_path = output_dir / f'xai_explanation_{diagnosis_id}.png'
    xai.save_explanation(fig, output_path)
    return str(output_path)