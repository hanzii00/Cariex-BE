from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMultiAlternatives
from django.http import HttpResponse
from django.contrib.auth import authenticate
from ..models import User
from ..serializers import RegisterSerializer, UserSerializer


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        
        # Build URL using request instead of get_current_site
        protocol = 'https' if request.is_secure() else 'http'
        host = request.get_host()
        verification_url = f"{protocol}://{host}/api/auth/verify/{user.verification_token}/"

        # HTML email content
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="UTF-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <title>Verify Your Email</title>
        </head>
        <body style="font-family: Arial, sans-serif; background-color: #f5f5f5; margin: 0; padding: 20px;">
          <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
            <tr>
              <td style="background-color: #4F46E5; padding: 30px; text-align: center;">
                <h1 style="color: #ffffff; margin: 0; font-size: 24px;">Confirm Your Email</h1>
              </td>
            </tr>
            <tr>
              <td style="padding: 40px 30px;">
                <p style="color: #333333; font-size: 16px; line-height: 1.5; margin: 0 0 20px 0;">
                  Hello {user.first_name} {user.last_name},<br><br>
                  Please confirm your email address by clicking the button below.
                </p>
                <table width="100%" cellpadding="0" cellspacing="0">
                  <tr>
                    <td align="center" style="padding: 20px 0;">
                      <a href="{verification_url}" style="display: inline-block; padding: 14px 32px; background-color: #4F46E5; color: #ffffff; text-decoration: none; border-radius: 6px; font-size: 16px; font-weight: 600;">
                        Verify Email
                      </a>
                    </td>
                  </tr>
                </table>
                <p style="color: #666666; font-size: 14px; margin: 20px 0 0 0;">
                  If the button doesn't work, copy and paste this link into your browser:
                </p>
                <p style="color: #4F46E5; font-size: 14px; word-break: break-all; margin: 10px 0 0 0;">
                  {verification_url}
                </p>
              </td>
            </tr>
          </table>
        </body>
        </html>
        """

        text_content = f"""
        Hello {user.first_name} {user.last_name},

        Please confirm your email address by visiting the link below:
        {verification_url}
        """

        email = EmailMultiAlternatives(
            subject='Confirm Your Email',
            body=text_content,
            from_email='Cariex Support',
            to=[user.email]
        )
        email.attach_alternative(html_content, "text/html")

        try:
            email.send()
            print(f"Email sent successfully to {user.email}")
        except Exception as e:
            print(f"Email sending failed: {str(e)}")

        return Response({
            'message': 'User registered successfully. Please check your email to verify your account.',
            'user': UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)

    print(f"Registration failed: {serializer.errors}")
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([AllowAny])
def verify_email(request, token):
    try:
        user = User.objects.get(verification_token=token)
        if not user.is_verified:
            user.is_verified = True
            user.is_active = True
            user.save()
            
            # Return nice HTML page
            html = """
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Email Verified</title>
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
                    .success-icon {
                        font-size: 60px;
                        color: #4F46E5;
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
                    .btn:hover {
                        background-color: #4338CA;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="success-icon">✓</div>
                    <h1>Email Verified Successfully!</h1>
                    <p>Your account has been verified. You can now log in to your account.</p>
                    <a href="http://localhost:3000/authentication" class="btn">Go to Login</a>
                </div>
            </body>
            </html>
            """
            return HttpResponse(html)
            
        else:
            html = """
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Already Verified</title>
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
                    .info-icon {
                        font-size: 60px;
                        color: #3B82F6;
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
                        background-color: #3B82F6;
                        color: white;
                        text-decoration: none;
                        border-radius: 6px;
                        font-weight: 600;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="info-icon">ℹ</div>
                    <h1>Already Verified</h1>
                    <p>Your email has already been verified. You can log in to your account.</p>
                    <a href="http://localhost:3000/authentication" class="btn">Go to Login</a>
                </div>
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
                <h1>Invalid Verification Link</h1>
                <p>This verification link is invalid or has expired. Please contact support if you need assistance.</p>
            </div>
        </body>
        </html>
        """
        return HttpResponse(html)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    email = request.data.get('email')
    password = request.data.get('password')
    
    if not email or not password:
        return Response({'error': 'Please provide both email and password.'}, 
                       status=status.HTTP_400_BAD_REQUEST)
    
    user = authenticate(username=email, password=password)
    
    if user is None:
        return Response({'error': 'Invalid credentials.'}, 
                       status=status.HTTP_401_UNAUTHORIZED)
    
    if not user.is_verified:
        return Response({'error': 'Please verify your email before logging in.'}, 
                       status=status.HTTP_403_FORBIDDEN)
    
    # Generate JWT tokens
    refresh = RefreshToken.for_user(user)
    
    return Response({
        'refresh': str(refresh),
        'access': str(refresh.access_token),
        'user': UserSerializer(user).data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def logout(request):
    """
    Logout endpoint that blacklists the refresh token.
    Note: Permission set to AllowAny because the token might be expired,
    but we still want to allow logout.
    """
    try:
        refresh_token = request.data.get('refresh')
        
        if not refresh_token:
            return Response(
                {'error': 'Refresh token is required.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        token = RefreshToken(refresh_token)
        token.blacklist()
        
        return Response(
            {'message': 'Logout successful.'}, 
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return Response(
            {'message': 'Logout successful.'}, 
            status=status.HTTP_200_OK
        )


# @api_view(['GET', 'PUT', 'PATCH'])
# @permission_classes([IsAuthenticated])
# def profile(request):
#     """
#     GET: Retrieve user profile
#     PUT/PATCH: Update user profile
#     """
#     user = request.user
    
#     if request.method == 'GET':
#         return Response(UserSerializer(user).data, status=status.HTTP_200_OK)
    
#     elif request.method in ['PUT', 'PATCH']:
#         # Import the serializer (add to imports at top of file)
#         from ..serializers import UserUpdateSerializer
        
#         serializer = UserUpdateSerializer(
#             user, 
#             data=request.data, 
#             partial=True,  # Allow partial updates
#             context={'request': request}
#         )
        
#         if serializer.is_valid():
#             serializer.save()
#             return Response({
#                 'message': 'Profile updated successfully.',
#                 'user': UserSerializer(user).data
#             }, status=status.HTTP_200_OK)
        
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

