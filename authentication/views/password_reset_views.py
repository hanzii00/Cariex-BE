from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMultiAlternatives
from django.http import HttpResponse
from ..models import User
from ..serializers import PasswordResetRequestSerializer, PasswordResetConfirmSerializer


@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_request(request):
    """
    Request a password reset. Sends an email with a reset link.
    """
    serializer = PasswordResetRequestSerializer(data=request.data)
    
    if serializer.is_valid():
        email = serializer.validated_data['email']
        
        try:
            user = User.objects.get(email=email)
            
            # Generate reset token
            reset_token = user.create_reset_token()
            
            # Build reset URL
            current_site = get_current_site(request)
            reset_url = f"http://{current_site.domain}/api/auth/password-reset/{reset_token}/"
            
            # HTML email content
            html_content = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
              <meta charset="UTF-8">
              <meta name="viewport" content="width=device-width, initial-scale=1.0">
              <title>Reset Your Password</title>
            </head>
            <body style="font-family: Arial, sans-serif; background-color: #f5f5f5; margin: 0; padding: 20px;">
              <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                
                <tr>
                  <td style="background-color: #4F46E5; padding: 30px; text-align: center;">
                    <h1 style="color: #ffffff; margin: 0; font-size: 24px;">Reset Your Password</h1>
                  </td>
                </tr>
                
                <tr>
                  <td style="padding: 40px 30px;">
                    <p style="color: #333333; font-size: 16px; line-height: 1.5; margin: 0 0 20px 0;">
                      Hello {user.username},<br><br>
                      We received a request to reset your password. Click the button below to create a new password.
                    </p>
                    
                    <table width="100%" cellpadding="0" cellspacing="0">
                      <tr>
                        <td align="center" style="padding: 20px 0;">
                          <a href="{reset_url}" style="display: inline-block; padding: 14px 32px; background-color: #4F46E5; color: #ffffff; text-decoration: none; border-radius: 6px; font-size: 16px; font-weight: 600;">
                            Reset Password
                          </a>
                        </td>
                      </tr>
                    </table>
                    
                    <p style="color: #666666; font-size: 14px; line-height: 1.5; margin: 20px 0 0 0;">
                      If the button doesn't work, copy and paste this link into your browser:
                    </p>
                    <p style="color: #4F46E5; font-size: 14px; word-break: break-all; margin: 10px 0 0 0;">
                      {reset_url}
                    </p>
                    
                    <p style="color: #EF4444; font-size: 14px; line-height: 1.5; margin: 20px 0 0 0; padding: 15px; background-color: #FEF2F2; border-radius: 6px;">
                      ⚠️ This link will expire in 24 hours.
                    </p>
                  </td>
                </tr>
                
                <tr>
                  <td style="background-color: #f9fafb; padding: 20px 30px; border-top: 1px solid #e5e7eb;">
                    <p style="color: #9ca3af; font-size: 13px; line-height: 1.5; margin: 0; text-align: center;">
                      If you didn't request a password reset, you can safely ignore this email. Your password will not be changed.
                    </p>
                  </td>
                </tr>
                
              </table>
            </body>
            </html>
            """
            
            # Plain text fallback
            text_content = f"""
            Hello {user.username},
            
            We received a request to reset your password. Click the link below to create a new password:
            
            {reset_url}
            
            This link will expire in 24 hours.
            
            If you didn't request a password reset, please ignore this email.
            """
            
            email_msg = EmailMultiAlternatives(
                subject='Reset Your Password',
                body=text_content,
                from_email='bhanzchester@gmail.com',
                to=[user.email]
            )
            email_msg.attach_alternative(html_content, "text/html")
            
            try:
                email_msg.send()
                print(f"Password reset email sent to {user.email}")
            except Exception as e:
                print(f"Email sending failed: {str(e)}")
            
        except User.DoesNotExist:
            # Don't reveal that the user doesn't exist
            pass
        
        # Always return success to prevent email enumeration
        return Response({
            'message': 'If an account with that email exists, a password reset link has been sent.'
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def password_reset_verify(request, token):
    """
    GET: Verify the reset token and show a form to enter new password.
    POST: Process the form submission and reset the password.
    """
    if request.method == 'GET':
        try:
            user = User.objects.get(reset_token=token)
            
            if not user.is_reset_token_valid():
                html = """
                <!DOCTYPE html>
                <html lang="en">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>Link Expired</title>
                    <style>
                        body {
                            font-family: Arial, sans-serif;
                            background-color: #f5f5f5;
                            display: flex;
                            justify-content: center;
                            align-items: center;
                            min-height: 100vh;
                            margin: 0;
                        }
                        .container {
                            background: white;
                            padding: 40px;
                            border-radius: 8px;
                            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                            text-align: center;
                            max-width: 500px;
                        }
                        .error-icon {
                            font-size: 60px;
                            color: #EF4444;
                            margin-bottom: 20px;
                        }
                        h1 {
                            color: #333;
                            margin-bottom: 15px;
                        }
                        p {
                            color: #666;
                            line-height: 1.6;
                            margin-bottom: 30px;
                        }
                        .btn {
                            display: inline-block;
                            padding: 12px 30px;
                            background-color: #4F46E5;
                            color: white;
                            text-decoration: none;
                            border-radius: 6px;
                            font-weight: 600;
                        }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="error-icon">⏱</div>
                        <h1>Link Expired</h1>
                        <p>This password reset link has expired. Please request a new password reset.</p>
                        <a href="http://localhost:3000/forgot-password" class="btn">Request New Link</a>
                    </div>
                </body>
                </html>
                """
                return HttpResponse(html)
            
            # Return HTML form for password reset
            html = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Reset Password</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        background-color: #f5f5f5;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        min-height: 100vh;
                        margin: 0;
                    }}
                    .container {{
                        background: white;
                        padding: 40px;
                        border-radius: 8px;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                        max-width: 500px;
                        width: 100%;
                    }}
                    h1 {{
                        color: #333;
                        margin-bottom: 10px;
                        text-align: center;
                    }}
                    p {{
                        color: #666;
                        line-height: 1.6;
                        margin-bottom: 30px;
                        text-align: center;
                    }}
                    .form-group {{
                        margin-bottom: 20px;
                    }}
                    label {{
                        display: block;
                        color: #333;
                        margin-bottom: 8px;
                        font-weight: 600;
                    }}
                    input {{
                        width: 100%;
                        padding: 12px;
                        border: 1px solid #ddd;
                        border-radius: 6px;
                        font-size: 16px;
                        box-sizing: border-box;
                    }}
                    input:focus {{
                        outline: none;
                        border-color: #4F46E5;
                    }}
                    .btn {{
                        width: 100%;
                        padding: 14px;
                        background-color: #4F46E5;
                        color: white;
                        border: none;
                        border-radius: 6px;
                        font-size: 16px;
                        font-weight: 600;
                        cursor: pointer;
                        margin-top: 10px;
                    }}
                    .btn:hover {{
                        background-color: #4338CA;
                    }}
                    .btn:disabled {{
                        background-color: #9CA3AF;
                        cursor: not-allowed;
                    }}
                    .error {{
                        color: #EF4444;
                        font-size: 14px;
                        margin-top: 5px;
                    }}
                    .success {{
                        color: #10B981;
                        font-size: 14px;
                        text-align: center;
                        margin-bottom: 20px;
                    }}
                    .message {{
                        padding: 12px;
                        border-radius: 6px;
                        margin-bottom: 20px;
                        text-align: center;
                    }}
                    .message.error {{
                        background-color: #FEE2E2;
                        color: #DC2626;
                    }}
                    .message.success {{
                        background-color: #D1FAE5;
                        color: #059669;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Reset Your Password</h1>
                    <p>Enter your new password below</p>
                    
                    <div id="message"></div>
                    
                    <form id="resetForm">
                        <div class="form-group">
                            <label for="password">New Password</label>
                            <input type="password" id="password" name="password" required minlength="8">
                            <div id="passwordError" class="error"></div>
                        </div>
                        
                        <div class="form-group">
                            <label for="password2">Confirm Password</label>
                            <input type="password" id="password2" name="password2" required minlength="8">
                            <div id="password2Error" class="error"></div>
                        </div>
                        
                        <button type="submit" class="btn" id="submitBtn">Reset Password</button>
                    </form>
                </div>
                
                <script>
                    document.getElementById('resetForm').addEventListener('submit', async (e) => {{
                        e.preventDefault();
                        
                        const submitBtn = document.getElementById('submitBtn');
                        const messageDiv = document.getElementById('message');
                        const password = document.getElementById('password').value;
                        const password2 = document.getElementById('password2').value;
                        
                        // Clear previous errors
                        document.getElementById('passwordError').textContent = '';
                        document.getElementById('password2Error').textContent = '';
                        messageDiv.textContent = '';
                        messageDiv.className = 'message';
                        
                        // Client-side validation
                        if (password !== password2) {{
                            document.getElementById('password2Error').textContent = "Passwords don't match";
                            return;
                        }}
                        
                        submitBtn.disabled = true;
                        submitBtn.textContent = 'Resetting...';
                        
                        try {{
                            const response = await fetch(window.location.href, {{
                                method: 'POST',
                                headers: {{
                                    'Content-Type': 'application/json',
                                }},
                                body: JSON.stringify({{
                                    password: password,
                                    password2: password2
                                }})
                            }});
                            
                            const data = await response.json();
                            
                            if (response.ok) {{
                                messageDiv.className = 'message success';
                                messageDiv.textContent = data.message;
                                document.getElementById('resetForm').reset();
                                
                                // Redirect to login after 2 seconds
                                setTimeout(() => {{
                                    window.location.href = 'http://localhost:3000/authentication';
                                }}, 2000);
                            }} else {{
                                messageDiv.className = 'message error';
                                if (data.password) {{
                                    document.getElementById('passwordError').textContent = data.password.join(' ');
                                }}
                                if (data.password2) {{
                                    document.getElementById('password2Error').textContent = data.password2.join(' ');
                                }}
                                if (data.error) {{
                                    messageDiv.textContent = data.error;
                                }}
                                submitBtn.disabled = false;
                                submitBtn.textContent = 'Reset Password';
                            }}
                        }} catch (error) {{
                            messageDiv.className = 'message error';
                            messageDiv.textContent = 'An error occurred. Please try again.';
                            submitBtn.disabled = false;
                            submitBtn.textContent = 'Reset Password';
                        }}
                    }});
                </script>
            </body>
            </html>
            """
            return HttpResponse(html)
            
        except User.DoesNotExist:
            html = """
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Invalid Link</title>
                <style>
                    body {
                        font-family: Arial, sans-serif;
                        background-color: #f5f5f5;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        min-height: 100vh;
                        margin: 0;
                    }
                    .container {
                        background: white;
                        padding: 40px;
                        border-radius: 8px;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                        text-align: center;
                        max-width: 500px;
                    }
                    .error-icon {
                        font-size: 60px;
                        color: #EF4444;
                        margin-bottom: 20px;
                    }
                    h1 {
                        color: #333;
                        margin-bottom: 15px;
                    }
                    p {
                        color: #666;
                        line-height: 1.6;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="error-icon">✗</div>
                    <h1>Invalid Reset Link</h1>
                    <p>This password reset link is invalid. Please request a new password reset.</p>
                </div>
            </body>
            </html>
            """
            return HttpResponse(html)
    
    # POST request - process password reset
    elif request.method == 'POST':
        return password_reset_confirm(request, token)


def password_reset_confirm(request, token):
    """
    Confirm password reset with new password.
    This is called by the POST request from password_reset_verify.
    """
    serializer = PasswordResetConfirmSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = User.objects.get(reset_token=token)
        
        if not user.is_reset_token_valid():
            return Response({
                'error': 'This password reset link has expired. Please request a new one.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Set new password
        user.set_password(serializer.validated_data['password'])
        user.reset_token = None
        user.reset_token_created = None
        user.save()
        
        return Response({
            'message': 'Password has been reset successfully. You can now log in with your new password.'
        }, status=status.HTTP_200_OK)
        
    except User.DoesNotExist:
        return Response({
            'error': 'Invalid reset token.'
        }, status=status.HTTP_400_BAD_REQUEST)