import tensorflow as tf
import numpy as np
from pathlib import Path

model_path = Path(__file__).parent / 'adult_teeth.h5'

print(f"Looking for model at: {model_path}")
print(f"Model exists: {model_path.exists()}")

if model_path.exists():
    try:
        print("\nAttempting to load model without compilation...")
        model = tf.keras.models.load_model(str(model_path), compile=False)
        
        print("\n✓ Model loaded successfully (without compilation)!")
        print(f"Input shape: {model.input_shape}")
        print(f"Output shape: {model.output_shape}")
        print(f"\nNumber of layers: {len(model.layers)}")
        print(f"Model has {model.count_params():,} parameters")
        
        print("\nModel summary:")
        model.summary()
        
        input_shape = model.input_shape[1:]  # Remove batch dimension
        print(f"\nCreating test input with shape: (1, {', '.join(map(str, input_shape))})")
        dummy_input = np.random.rand(1, *input_shape).astype(np.float32)
        
        print("Running test prediction...")
        prediction = model.predict(dummy_input, verbose=0)
        print(f"\n✓ Test prediction successful!")
        print(f"Output shape: {prediction.shape}")
        print(f"Output values: {prediction}")
        
        # Analyze output
        if prediction.shape[-1] > 1:
            print(f"\nThis appears to be a classification model with {prediction.shape[-1]} classes")
            print(f"Predicted class: {np.argmax(prediction)}")
            print(f"Class probabilities: {prediction[0]}")
        else:
            print(f"\nThis appears to be a regression or binary classification model")
            print(f"Output value: {prediction[0][0]}")
            
    except Exception as e:
        print(f"\n✗ Error loading model: {e}")
        print("\nTrying alternative loading method...")
        
        try:
            # Try loading with custom objects
            model = tf.keras.models.load_model(
                str(model_path),
                compile=False,
                custom_objects=None
            )
            print("✓ Model loaded with alternative method!")
            print(f"Input shape: {model.input_shape}")
            print(f"Output shape: {model.output_shape}")
        except Exception as e2:
            print(f"✗ Alternative method also failed: {e2}")
else:
    print("\n✗ Model file not found!")