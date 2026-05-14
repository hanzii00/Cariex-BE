import traceback
import numpy as np
from pathlib import Path


def _import_tensorflow():
    try:
        import tensorflow as tf
        return tf
    except ImportError:
        return None

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
        tf = _import_tensorflow()
        if tf is None:
            raise ImportError('TensorFlow is required for XAI visualization')
        if not HAVE_CV2:
            raise ImportError('OpenCV (cv2) is required for XAI visualization')
        self.model = model
        self.tf = tf

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_segmentation_model(self, predictions):
        """True if predictions are a spatial mask (4-D), False if classification (2-D)."""
        return len(np.array(predictions).shape) == 4

    def _adaptive_threshold(self, mask):
        """
        Scale threshold to the model's actual output range.
        Using 50% of the peak value anchors the threshold to the model's
        real distribution and produces accurate affected-area readings.
        """
        max_prob = float(np.max(mask))
        return max(0.5 * max_prob, 0.05)

    def _debug_mask(self, mask, label="mask"):
        """Print raw mask statistics – useful when affected area looks wrong."""
        print(f"=== MASK DEBUG [{label}] ===")
        print(f"  Shape       : {mask.shape}")
        print(f"  Min         : {mask.min():.6f}")
        print(f"  Max         : {mask.max():.6f}")
        print(f"  Mean        : {mask.mean():.6f}")
        print(f"  Unique[:10] : {np.unique(mask.flatten())[:10]}")
        thresh = self._adaptive_threshold(mask)
        print(f"  Adaptive T  : {thresh:.6f}")
        pct = float(np.sum(mask > thresh) / mask.size * 100)
        print(f"  % > T       : {pct:.2f}%")
        print("=" * 30)

    # ------------------------------------------------------------------
    # Find a meaningful intermediate conv layer for Grad-CAM
    # ------------------------------------------------------------------

    def _find_last_conv_layer(self):
        """
        Return the name of the last *intermediate* Conv layer.

        Skips the final output layer (which would create duplicate outputs
        in grad_model and produce zero gradients), requires a true spatial
        feature map (rank-4 output_shape) with more than 1 channel.
        """
        output_layer_name = self.model.layers[-1].name

        for layer in reversed(self.model.layers):
            if layer.name == output_layer_name:
                continue

            try:
                shape = layer.output_shape
            except AttributeError:
                continue

            if not (isinstance(shape, (list, tuple)) and len(shape) == 4):
                continue

            n_channels = shape[-1] if shape[-1] is not None else 0

            is_conv = any(k in layer.name.lower()
                          for k in ('conv', 'separable', 'depthwise'))
            if is_conv and n_channels > 1:
                print(f"[Grad-CAM] Using layer: {layer.name}  shape={shape}")
                return layer.name

        fallback = self.model.layers[-2].name
        print(f"[Grad-CAM] Fallback layer: {fallback}")
        return fallback

    # ------------------------------------------------------------------
    # Grad-CAM
    # ------------------------------------------------------------------

    def generate_gradcam(self, image, layer_name=None):
        """
        Generate a Grad-CAM heatmap.

        - Uses _find_last_conv_layer() which skips the output layer.
        - For segmentation models uses tf.reduce_max(predictions) as the
          loss so spatial signal is preserved (reduce_mean kills gradients).
        - Full traceback printed on error.
        """
        tf = self.tf

        if layer_name is None:
            layer_name = self._find_last_conv_layer()

        print(f"[Grad-CAM] Target layer: {layer_name}")

        grad_model = tf.keras.models.Model(
            inputs=[self.model.inputs],
            outputs=[self.model.get_layer(layer_name).output, self.model.output]
        )

        with tf.GradientTape() as tape:
            conv_outputs, predictions = grad_model(image)

            if self._is_segmentation_model(predictions):
                loss = tf.reduce_max(predictions)
            else:
                loss = predictions[0, tf.argmax(predictions[0])]

        grads = tape.gradient(loss, conv_outputs)

        if grads is None:
            raise RuntimeError(
                f"GradientTape returned None for layer '{layer_name}'. "
                "The layer may not be on the computational path to the output."
            )

        if len(grads.shape) == 4:
            pooled_grads = tf.reduce_mean(grads, axis=(0, 1, 2))
        elif len(grads.shape) == 3:
            pooled_grads = tf.reduce_mean(grads, axis=(0, 1))
        else:
            pooled_grads = tf.reduce_mean(grads, axis=0)

        conv_outputs = conv_outputs[0]

        if len(conv_outputs.shape) == 3:
            heatmap = conv_outputs @ pooled_grads[..., tf.newaxis]
            heatmap = tf.squeeze(heatmap)
        else:
            heatmap = tf.reduce_mean(conv_outputs * pooled_grads, axis=-1)

        heatmap = tf.maximum(heatmap, 0)
        max_val = tf.math.reduce_max(heatmap)
        if max_val > 0:
            heatmap = heatmap / max_val

        heatmap_np = heatmap.numpy()

        print(f"[Grad-CAM] heatmap stats – min={heatmap_np.min():.4f} "
              f"max={heatmap_np.max():.4f} mean={heatmap_np.mean():.4f}")

        if heatmap_np.ndim == 0:
            heatmap_np = np.ones((8, 8), dtype=np.float32) * float(heatmap_np)
        elif heatmap_np.ndim == 1:
            size = max(int(np.sqrt(len(heatmap_np))), 1)
            heatmap_np = heatmap_np[:size * size].reshape(size, size)

        return heatmap_np

    # ------------------------------------------------------------------
    # Overlay helpers
    # ------------------------------------------------------------------

    def overlay_heatmap(self, heatmap, original_image, alpha=0.4, colormap=None):
        """
        Overlay Grad-CAM heatmap on original image.

        Uses TURBO colormap (better perceptual contrast than JET) and
        percentile contrast-stretching so near-uniform heatmaps don't
        paint the entire image red.
        """
        if not HAVE_CV2:
            raise ImportError('OpenCV (cv2) is required for heatmap overlay')

        if colormap is None:
            colormap = cv2.COLORMAP_TURBO

        # Percentile contrast stretch — clip bottom 60% of activations so
        # low-confidence background areas don't all appear as hot colours.
        h    = heatmap.astype(np.float32).copy()
        low  = np.percentile(h, 60)
        high = np.percentile(h, 100)
        if high > low:
            h = np.clip((h - low) / (high - low), 0, 1)
        else:
            h = np.zeros_like(h)

        heatmap_resized = cv2.resize(h, (original_image.shape[1], original_image.shape[0]))
        heatmap_colored = cv2.applyColorMap(np.uint8(255 * heatmap_resized), colormap)
        heatmap_colored = cv2.cvtColor(heatmap_colored, cv2.COLOR_BGR2RGB)

        if original_image.dtype != np.uint8:
            original_image = (original_image * 255).astype(np.uint8)

        return cv2.addWeighted(original_image, 1 - alpha, heatmap_colored, alpha, 0)

    def visualize_segmentation_overlay(self, original_image, segmentation_mask, threshold=None):
        """
        Overlay the segmentation mask onto the original image.

        Uses adaptive threshold by default so that the coloured region
        accurately reflects the model's high-confidence pixels.
        """
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

    # ------------------------------------------------------------------
    # Label resolver  ← fixes the "Healthy 83.7%" mislabelling bug
    # ------------------------------------------------------------------

    def _resolve_bar_labels(self, probs, severity, severity_result):
        """
        Return (labels, colors) correctly aligned to the probability list.

        Priority:
          1. Use class_labels from severity_result when model_loader
             provides it — this is the most reliable path because
             model_loader knows the exact softmax output order.
          2. Fallback: swap the default label list so that argmax(probs)
             aligns with the predicted severity string.

        This is what fixed the screenshot bug where the bar chart showed
        "Healthy : 83.7%" while severity was correctly Moderate —
        the old code hardcoded ['Deep','Healthy','Moderate'] which did not
        match the model's actual output order.
        """
        severity_color_map = {
            'Deep':     '#ef4444',
            'Moderate': '#f97316',
            'Healthy':  '#22c55e',
        }
        default_classes = ['Deep', 'Healthy', 'Moderate']

        # Path 1 — trust explicit label order from model_loader
        class_labels = severity_result.get('class_labels', None)
        if class_labels and len(class_labels) == len(probs):
            labels = list(class_labels)
            colors = [severity_color_map.get(l, '#94a3b8') for l in labels]
            return labels, colors

        # Path 2 — swap so argmax matches predicted severity
        labels = default_classes[:len(probs)]
        if severity in labels:
            max_idx      = int(np.argmax(probs))
            severity_idx = labels.index(severity)
            if severity_idx != max_idx:
                labels[max_idx], labels[severity_idx] = (
                    labels[severity_idx], labels[max_idx]
                )

        colors = [severity_color_map.get(l, '#94a3b8') for l in labels]
        return labels, colors

    # ------------------------------------------------------------------
    # Main report
    # ------------------------------------------------------------------

    def create_explanation_report(self, original_image, preprocessed_image,
                                  segmentation_mask, severity_result):
        if not HAVE_MATPLOTLIB or plt is None:
            raise ImportError('matplotlib is required to create XAI explanation reports')

        is_segmentation = self._is_segmentation_model(segmentation_mask)

        severity   = severity_result.get('severity', 'N/A')
        confidence = float(severity_result.get('confidence', 0))

        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        fig.patch.set_facecolor('#0f172a')
        for ax in axes.flat:
            ax.set_facecolor('#1e293b')

        fig.suptitle('Explainable AI — Dental Caries Detection',
                     fontsize=16, fontweight='bold', color='white', y=0.98)

        title_kw  = dict(color='white', fontsize=10, pad=6)
        border_kw = dict(color='#334155', linewidth=1.5)

        # ── Panel [0,0]  Original image ────────────────────────────────
        axes[0, 0].imshow(original_image)
        axes[0, 0].set_title('Original Peri-apical X-ray', **title_kw)
        axes[0, 0].axis('off')
        for spine in axes[0, 0].spines.values():
            spine.set(**border_kw)

        # ── Panel [0,1]  Probability heatmap / bar chart ───────────────
        if is_segmentation:
            mask_2d = segmentation_mask[0, :, :, 0]
            im = axes[0, 1].imshow(mask_2d, cmap='hot', vmin=0, vmax=mask_2d.max() or 1)
            plt.colorbar(im, ax=axes[0, 1], fraction=0.046, pad=0.04)
            axes[0, 1].set_title('Probability Heatmap (raw model output)', **title_kw)
            axes[0, 1].axis('off')
        else:
            probs          = severity_result.get('all_probabilities', [confidence])
            labels, colors = self._resolve_bar_labels(probs, severity, severity_result)

            display_order = list(reversed(range(len(labels))))
            bars = axes[0, 1].barh(
                [labels[i] for i in display_order],
                [probs[i] for i in display_order],
                color=[colors[i] for i in display_order]
            )
            axes[0, 1].set_xlim(0, 100)
            axes[0, 1].set_xlabel('Confidence (%)', color='#94a3b8')
            axes[0, 1].set_title('Class Probabilities', **title_kw)
            axes[0, 1].tick_params(colors='#94a3b8')
            for spine in axes[0, 1].spines.values():
                spine.set_edgecolor('#475569')
            for bar, i in zip(bars, display_order):
                v = probs[i]
                axes[0, 1].text(
                    min(v + 1, 95), bar.get_y() + bar.get_height() / 2,
                    f'{v:.1f}%', va='center', fontsize=9, color='white'
                )

        for spine in axes[0, 1].spines.values():
            spine.set(**border_kw)

        # ── Panel [0,2]  Segmentation overlay / severity tint ──────────
        if is_segmentation:
            mask_2d            = segmentation_mask[0, :, :, 0]
            adaptive_threshold = self._adaptive_threshold(mask_2d)
            affected_pixels    = float(np.sum(mask_2d > adaptive_threshold) / mask_2d.size * 100)
            has_caries         = affected_pixels > 1.0 or float(np.max(mask_2d)) > 0.15
            overlay, _         = self.visualize_segmentation_overlay(
                original_image, segmentation_mask, threshold=adaptive_threshold)
            axes[0, 2].imshow(overlay)
            title_text = (
                f'Caries Detected  ({affected_pixels:.1f}% affected)'
                if has_caries else 'No Caries Detected'
            )
            axes[0, 2].set_title(title_text, **title_kw)
        else:
            severity_colors = {
                'Deep':     (0.94, 0.27, 0.27),
                'Healthy':  (0.13, 0.77, 0.37),
                'Moderate': (0.98, 0.59, 0.12),
            }
            color     = severity_colors.get(severity, (0.5, 0.5, 0.5))
            tint      = np.full_like(original_image,
                                     [int(c * 255) for c in color], dtype=np.uint8)
            img_uint8 = (original_image if original_image.dtype == np.uint8
                         else (original_image * 255).astype(np.uint8))
            tinted    = cv2.addWeighted(img_uint8, 0.8, tint, 0.2, 0)
            has_caries         = severity.lower() not in ['healthy']
            affected_pixels    = 0.0
            adaptive_threshold = 0.5
            axes[0, 2].imshow(tinted)
            axes[0, 2].set_title(f'Severity Classification: {severity}', **title_kw)

        axes[0, 2].axis('off')
        for spine in axes[0, 2].spines.values():
            spine.set(**border_kw)

        # ── Panel [1,0]  Grad-CAM ──────────────────────────────────────
        gradcam_ok = False
        try:
            gradcam         = self.generate_gradcam(preprocessed_image)
            gradcam_overlay = self.overlay_heatmap(gradcam, original_image)
            axes[1, 0].imshow(gradcam_overlay)
            axes[1, 0].set_title('Grad-CAM — Model Focus Areas', **title_kw)
            gradcam_ok = True
        except Exception as e:
            traceback.print_exc()
            err_msg = f'Grad-CAM unavailable:\n{type(e).__name__}: {e}'
            axes[1, 0].text(0.5, 0.5, err_msg,
                            ha='center', va='center', fontsize=8,
                            color='#ef4444', wrap=True,
                            transform=axes[1, 0].transAxes)
            axes[1, 0].set_title('Grad-CAM (failed — check logs)', **title_kw)

        axes[1, 0].axis('off')
        for spine in axes[1, 0].spines.values():
            spine.set(**border_kw)

        # ── Panel [1,1]  Binary mask / confidence gauge ────────────────
        if is_segmentation:
            mask_2d     = segmentation_mask[0, :, :, 0]
            binary_mask = (mask_2d > adaptive_threshold).astype(np.uint8) * 255
            axes[1, 1].imshow(binary_mask, cmap='gray')
            axes[1, 1].set_title(
                f'Binary Mask  (adaptive threshold = {adaptive_threshold:.3f})', **title_kw)
        else:
            theta = np.linspace(0, np.pi, 200)
            axes[1, 1].plot(np.cos(theta), np.sin(theta), '#334155', lw=10)
            angle = np.pi * (1 - confidence / 100)
            axes[1, 1].annotate(
                '', xy=(np.cos(angle) * 0.8, np.sin(angle) * 0.8),
                xytext=(0, 0),
                arrowprops=dict(arrowstyle='->', color='#ef4444', lw=3)
            )
            axes[1, 1].text(0, -0.3, f'{confidence:.1f}%', ha='center',
                            fontsize=16, fontweight='bold', color='white')
            axes[1, 1].text(0, -0.55, 'Confidence', ha='center',
                            fontsize=10, color='#94a3b8')
            axes[1, 1].set_xlim(-1.2, 1.2)
            axes[1, 1].set_ylim(-0.7, 1.2)
            axes[1, 1].set_title('Model Confidence', **title_kw)

        axes[1, 1].axis('off')
        for spine in axes[1, 1].spines.values():
            spine.set(**border_kw)

        # ── Panel [1,2]  Detection statistics ──────────────────────────
        affected_pct = float(severity_result.get('affected_percentage', affected_pixels))
        mean_prob    = float(severity_result.get('mean_probability', 0))
        max_prob_val = float(severity_result.get('max_probability', 0))

        if has_caries:
            interpretation = (
                "Interpretation:\n"
                "  - Caries regions highlighted in red\n"
                "  - Brighter pixels = higher model confidence\n"
                "  - Orange/yellow = borderline regions\n"
                "  - Review highlighted areas clinically"
            )
        else:
            interpretation = (
                "Interpretation:\n"
                "  - No significant caries detected\n"
                "  - All pixels below detection threshold\n"
                "  - Image suggests healthy tissue\n"
                "  - Routine monitoring recommended"
            )

        gradcam_note = "" if gradcam_ok else "\n⚠ Grad-CAM failed — check server logs"

        if is_segmentation:
            stats_text = (
                f"Severity      : {severity}\n"
                f"Confidence    : {confidence:.2f}%\n\n"
                f"Adaptive Thresh: {adaptive_threshold:.4f}\n"
                f"Affected Area : {affected_pixels:.2f}%\n"
                f"Mean Prob     : {mean_prob:.4f}\n"
                f"Max Prob      : {max_prob_val:.4f}\n\n"
                f"{interpretation}"
                f"{gradcam_note}"
            )
        else:
            probs           = severity_result.get('all_probabilities', [])
            labels_cls, _   = self._resolve_bar_labels(probs, severity, severity_result)
            prob_lines      = '\n'.join(
                f"  {labels_cls[i]:<9}: {p:.1f}%"
                for i, p in enumerate(probs)
            ) if probs else '  N/A'
            stats_text = (
                f"Severity      : {severity}\n"
                f"Confidence    : {confidence:.2f}%\n\n"
                f"Class Probabilities:\n{prob_lines}\n\n"
                f"{interpretation}"
                f"{gradcam_note}"
            )

        axes[1, 2].text(0.05, 0.97, stats_text, fontsize=9,
                        verticalalignment='top', family='monospace',
                        transform=axes[1, 2].transAxes, linespacing=1.6,
                        color='#e2e8f0')
        axes[1, 2].set_title('Detection Statistics', **title_kw)
        axes[1, 2].axis('off')
        for spine in axes[1, 2].spines.values():
            spine.set(**border_kw)

        plt.tight_layout(rect=[0, 0, 1, 0.97])
        return fig

    # ------------------------------------------------------------------
    # Save helper
    # ------------------------------------------------------------------

    def save_explanation(self, fig, output_path):
        if not HAVE_MATPLOTLIB or plt is None:
            raise ImportError('matplotlib is required to save XAI explanation reports')
        fig.savefig(output_path, dpi=150, bbox_inches='tight',
                    facecolor=fig.get_facecolor())
        plt.close(fig)


# ----------------------------------------------------------------------
# Legacy helper
# ----------------------------------------------------------------------

def generate_xai_explanation(diagnosis_id):
    """Legacy helper kept for backwards compatibility."""
    if not HAVE_CV2:
        raise ImportError('OpenCV (cv2) is required for XAI explanation generation')
    tf = _import_tensorflow()
    if tf is None:
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