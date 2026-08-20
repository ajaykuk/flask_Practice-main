# Flask Student App — Complete CI/CD with GitHub Actions, Amazon ECR, SSM and EC2

This project demonstrates an end-to-end CI/CD pipeline for a Flask application.

A push to `main` automatically:
1. Runs pytest.
2. Authenticates to AWS using GitHub OIDC.
3. Builds the Docker image.
4. Pushes the image to Amazon ECR.
5. Uses AWS Systems Manager (SSM) to deploy to EC2.
6. EC2 pulls the image, replaces the old container, and starts the new one.

## 1. Architecture

```text
Developer
   |
   | git push origin main
   v
GitHub Repository
   |
   v
GitHub Actions
   |
   +--> Checkout
   +--> Install Python dependencies
   +--> pytest
   +--> GitHub OIDC --> AWS STS --> GitHubActions-Flask-ECR-Role
   +--> Docker build
   +--> Docker push
   |
   +--> SSM SendCommand
             |
             v
          EC2
             |
             +--> docker login ECR
             +--> docker pull
             +--> docker stop old container
             +--> docker rm old container
             +--> docker run new container
             |
             v
       Flask container :5000
             |
             v
http://<EC2_PUBLIC_IP>:5000/health
```

![Complete CI/CD architecture diagram](a_clean_infographic_style_readme_poster_image_ove.png)

## 2. Technology Stack

| Component | Technology |
|---|---|
| Application | Python / Flask |
| Testing | pytest |
| Containerization | Docker |
| Source control | Git / GitHub |
| CI/CD | GitHub Actions |
| AWS authentication | GitHub OIDC |
| Container registry | Amazon ECR |
| Deployment | AWS Systems Manager (SSM) |
| Compute | Amazon EC2 |
| Database | MongoDB / MongoDB Atlas |
| Application port | 5000 |

## 3. Project Structure

```text
flask_Practice-main/
├── app.py
├── requirements.txt
├── Dockerfile
├── .dockerignore
├── .env.example
├── README.md
├── tests/
│   └── test_app.py
└── .github/
    └── workflows/
        └── ci-cd.yml
```

## 4. Flask Application

The application is started with:

```bash
python app.py
```

The application exposes:

```text
GET /health
```

Healthy response:

```json
{
  "status": "healthy",
  "database": "connected"
}
```

MongoDB failure response:

```json
{
  "status": "unhealthy",
  "database": "disconnected"
}
```

The failure response uses HTTP `503`.

## 5. Environment Variables

The Flask application uses:

```env
MONGO_URI=<your-mongodb-connection-string>
SECRET_KEY=<your-flask-secret-key>
```

Example:

```env
MONGO_URI=mongodb+srv://username:password@cluster.example.mongodb.net/test_student_db
SECRET_KEY=your-long-random-secret
```

Do **not** commit `.env` to Git.

Keep:

```text
.env
```

in `.gitignore`.

For this deployment, the production `.env` is stored directly on EC2:

```text
/home/ec2-user/.env
```

and supplied to Docker with:

```bash
--env-file /home/ec2-user/.env
```

## 6. Dockerfile

A suitable Dockerfile is:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "app.py"]
```

Build locally:

```bash
docker build -t flask-student-app .
```

Run locally:

```bash
docker run -d   --name flask-student-app   -p 5000:5000   --env-file .env   flask-student-app
```

Test:

```bash
curl http://localhost:5000/health
```

## 7. Tests

Run locally:

```bash
python -m pytest
```

GitHub Actions runs the same test suite before Docker build.

The pipeline is:

```text
pytest PASS --> Docker build --> ECR push --> EC2 deployment
pytest FAIL --> pipeline stops
```

## 8. AWS Resources

This project uses:

```text
AWS Account: 490600801130
Region: us-east-1

ECR repository:
flask-student-app

GitHub Actions IAM role:
GitHubActions-Flask-ECR-Role

EC2:
<YOUR_EC2_INSTANCE_ID>
```

## 9. Create the ECR Repository

Create the private ECR repository:

```bash
aws ecr create-repository   --repository-name flask-student-app   --region us-east-1
```

Verify:

```bash
aws ecr describe-repositories   --repository-names flask-student-app   --region us-east-1
```

The image URI is:

```text
490600801130.dkr.ecr.us-east-1.amazonaws.com/flask-student-app:latest
```

## 10. EC2 Setup

The EC2 instance is the machine where the Docker container runs.

Amazon Linux 2023 can be used.

### Install Docker

```bash
sudo dnf install -y docker
```

Start Docker:

```bash
sudo systemctl start docker
```

Enable Docker after reboot:

```bash
sudo systemctl enable docker
```

Check:

```bash
sudo systemctl status docker
```

Expected:

```text
Active: active (running)
```

Allow `ec2-user` to run Docker:

```bash
sudo usermod -aG docker ec2-user
```

Log out/in and verify:

```bash
docker ps
```

### Verify AWS CLI

```bash
aws --version
```

### Verify SSM Agent

```bash
sudo systemctl status amazon-ssm-agent
```

If necessary:

```bash
sudo systemctl start amazon-ssm-agent
```

## 11. EC2 IAM Role

The EC2 instance role needs at least:

```text
AmazonEC2ContainerRegistryReadOnly
AmazonSSMManagedInstanceCore
```

### AmazonEC2ContainerRegistryReadOnly

Allows EC2 to pull images from ECR.

```text
EC2 --> ECR: docker pull
```

### AmazonSSMManagedInstanceCore

Allows the SSM Agent on EC2 to communicate with Systems Manager.

```text
GitHub Actions --> SSM --> EC2 SSM Agent
```

Verify the instance is SSM-managed:

```bash
aws ssm describe-instance-information   --region us-east-1
```

## 12. GitHub Actions IAM Role

Create/use a separate IAM role for GitHub Actions:

```text
GitHubActions-Flask-ECR-Role
```

Do not reuse the EC2 instance role.

The responsibilities are:

```text
GitHubActions-Flask-ECR-Role
    |
    +--> ECR PUSH
    |
    +--> SSM SendCommand
    |
    +--> SSM GetCommandInvocation
```

The EC2 role is separate:

```text
EC2 Instance Role
    |
    +--> ECR PULL
    |
    +--> SSM Agent communication
```

## 13. GitHub OIDC Authentication

The GitHub Actions workflow uses OIDC rather than long-lived AWS access keys.

Flow:

```text
GitHub Actions
      |
      | OIDC token
      v
token.actions.githubusercontent.com
      |
      v
AWS STS
      |
      | AssumeRoleWithWebIdentity
      v
GitHubActions-Flask-ECR-Role
```

The workflow must have:

```yaml
permissions:
  id-token: write
  contents: read
```

No `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` GitHub secrets are required.

## 14. GitHub OIDC Provider

In IAM, configure:

```text
Provider:
https://token.actions.githubusercontent.com

Audience:
sts.amazonaws.com
```

The IAM role trust relationship must allow:

```text
sts:AssumeRoleWithWebIdentity
```

and restrict the `sub` condition to the intended GitHub repository/branch.

Generic example:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::490600801130:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:<GITHUB_OWNER>/<REPOSITORY>:ref:refs/heads/main"
        }
      }
    }
  ]
}
```

Replace the placeholders with the exact GitHub OIDC subject for your repository. The `sub` must match the actual token; do not assume the Docker Hub username is the GitHub owner.

## 15. GitHub Actions ECR Permissions

The GitHub Actions role needs ECR push permissions such as:

```text
ecr:GetAuthorizationToken
ecr:BatchCheckLayerAvailability
ecr:CompleteLayerUpload
ecr:InitiateLayerUpload
ecr:PutImage
ecr:UploadLayerPart
```

The repository resource can be scoped to:

```text
arn:aws:ecr:us-east-1:490600801130:repository/flask-student-app
```

`ecr:GetAuthorizationToken` normally uses `Resource: "*"`.

## 16. GitHub Actions SSM Permissions

The GitHub Actions role also needs deployment permissions such as:

```text
ssm:SendCommand
ssm:GetCommandInvocation
```

The deployment uses:

```text
AWS-RunShellScript
```

and targets the intended EC2 instance.

## 17. GitHub Repository Setup

The workflow file is:

```text
.github/workflows/ci-cd.yml
```

The pipeline is triggered by:

```yaml
on:
  push:
    branches:
      - main
```

It can also include:

```yaml
workflow_dispatch:
```

to provide a manual **Run workflow** button in GitHub Actions.

## 18. Complete `ci-cd.yml`

Use the following as the deployment workflow:

```yaml
name: Flask App CI/CD

on:
  push:
    branches:
      - main

  workflow_dispatch:

permissions:
  id-token: write
  contents: read

env:
  AWS_REGION: us-east-1
  ECR_REPOSITORY: flask-student-app
  IMAGE_TAG: latest
  INSTANCE_ID: i-XXXXXXXXXXXXXXXXX
  CONTAINER_NAME: flask-student-app

jobs:

  test:
    name: Run Tests
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest

      - name: Run pytest
        run: |
          python -m pytest


  build-and-push:
    name: Build and Push Docker Image
    needs: test
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::490600801130:role/GitHubActions-Flask-ECR-Role
          aws-region: ${{ env.AWS_REGION }}

      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build Docker image
        run: |
          docker build             -t ${{ steps.login-ecr.outputs.registry }}/${{ env.ECR_REPOSITORY }}:${{ env.IMAGE_TAG }} .

      - name: Push Docker image
        run: |
          docker push             ${{ steps.login-ecr.outputs.registry }}/${{ env.ECR_REPOSITORY }}:${{ env.IMAGE_TAG }}


  deploy:
    name: Deploy to EC2
    needs: build-and-push
    runs-on: ubuntu-latest

    steps:
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::490600801130:role/GitHubActions-Flask-ECR-Role
          aws-region: ${{ env.AWS_REGION }}

      - name: Deploy application to EC2
        run: |
          aws ssm send-command             --instance-ids "${{ env.INSTANCE_ID }}"             --document-name "AWS-RunShellScript"             --parameters 'commands=[
              "set -e",
              "echo Logging into ECR...",
              "aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 490600801130.dkr.ecr.us-east-1.amazonaws.com",
              "echo Pulling latest image...",
              "docker pull 490600801130.dkr.ecr.us-east-1.amazonaws.com/flask-student-app:latest",
              "echo Stopping old container...",
              "docker stop flask-student-app || true",
              "echo Removing old container...",
              "docker rm flask-student-app || true",
              "echo Starting new container...",
              "docker run -d --name flask-student-app --restart unless-stopped -p 5000:5000 --env-file /home/ec2-user/.env 490600801130.dkr.ecr.us-east-1.amazonaws.com/flask-student-app:latest",
              "echo Deployment completed.",
              "docker ps"
            ]'
```

Replace:

```text
i-XXXXXXXXXXXXXXXXX
```

with your actual EC2 instance ID.

## 19. What Happens When You Push Code?

Run:

```bash
git add .
git commit -m "Update Flask application"
git push origin main
```

### Step 1 — GitHub Actions starts

GitHub sees a push to `main`.

### Step 2 — Checkout

The runner downloads the repository.

### Step 3 — Python setup

Python 3.12 is installed.

### Step 4 — Dependencies

```bash
pip install -r requirements.txt
```

### Step 5 — Tests

```bash
python -m pytest
```

If tests fail, deployment stops.

### Step 6 — OIDC

GitHub obtains an OIDC token and AWS STS assumes:

```text
GitHubActions-Flask-ECR-Role
```

### Step 7 — ECR login

GitHub Actions authenticates Docker to ECR.

### Step 8 — Docker build

The GitHub-hosted runner executes:

```bash
docker build
```

### Step 9 — Docker push

The image is pushed to:

```text
490600801130.dkr.ecr.us-east-1.amazonaws.com/flask-student-app:latest
```

### Step 10 — SSM deployment

GitHub Actions calls:

```bash
aws ssm send-command
```

### Step 11 — EC2 login to ECR

EC2 executes:

```bash
aws ecr get-login-password --region us-east-1   | docker login --username AWS --password-stdin   490600801130.dkr.ecr.us-east-1.amazonaws.com
```

### Step 12 — Pull

```bash
docker pull   490600801130.dkr.ecr.us-east-1.amazonaws.com/flask-student-app:latest
```

### Step 13 — Replace old container

```bash
docker stop flask-student-app || true
docker rm flask-student-app || true
```

### Step 14 — Start new container

```bash
docker run -d   --name flask-student-app   --restart unless-stopped   -p 5000:5000   --env-file /home/ec2-user/.env   490600801130.dkr.ecr.us-east-1.amazonaws.com/flask-student-app:latest
```

## 20. Important Docker Location

There are two different Docker environments in this architecture.

### GitHub Actions runner

Docker is used to:

```text
Build image
Push image
```

### EC2

Docker is used to:

```text
Pull image
Run container
```

Therefore, Docker does need to be installed and running on EC2.

Your Mac does not need to run Docker for the GitHub Actions deployment itself.

## 21. Application Access

If the EC2 public IP is:

```text
<EC2_PUBLIC_IP>
```

open:

```text
http://<EC2_PUBLIC_IP>:5000/
```

Health endpoint:

```text
http://<EC2_PUBLIC_IP>:5000/health
```

The EC2 Security Group must allow inbound TCP `5000` if the application is accessed directly.

For production, use Nginx or an Application Load Balancer and HTTPS instead of exposing Flask directly on port 5000.

## 22. Verify Deployment

On EC2:

```bash
docker ps
```

View logs:

```bash
docker logs flask-student-app
```

Follow logs:

```bash
docker logs -f flask-student-app
```

Health check:

```bash
curl http://localhost:5000/health
```

Expected:

```json
{
  "status": "healthy",
  "database": "connected"
}
```

## 23. Troubleshooting

### OIDC error

```text
Could not assume role with OIDC:
Not authorized to perform sts:AssumeRoleWithWebIdentity
```

Check:

- OIDC provider exists.
- Provider URL is `https://token.actions.githubusercontent.com`.
- Audience is `sts.amazonaws.com`.
- `id-token: write` is present.
- The role ARN in YAML is correct.
- The trust policy uses the correct GitHub OIDC `sub`.
- Repository owner/name and branch match exactly.

### ECR push denied

Check the GitHub Actions role has:

```text
ecr:GetAuthorizationToken
ecr:BatchCheckLayerAvailability
ecr:CompleteLayerUpload
ecr:InitiateLayerUpload
ecr:PutImage
ecr:UploadLayerPart
```

### EC2 cannot pull ECR image

Check EC2 has:

```text
AmazonEC2ContainerRegistryReadOnly
```

and:

```bash
aws --version
docker --version
```

### SSM cannot reach EC2

Check:

```bash
sudo systemctl status amazon-ssm-agent
```

and the EC2 role has:

```text
AmazonSSMManagedInstanceCore
```

### Docker permission denied on EC2

Run:

```bash
sudo usermod -aG docker ec2-user
```

Then log out/in.

### Port 5000 unavailable

On EC2:

```bash
docker ps
curl http://localhost:5000/health
```

If localhost works but the public IP does not, check the EC2 Security Group and OS firewall.

## 24. Security Best Practices

Use:

- GitHub OIDC instead of long-lived AWS keys.
- A dedicated GitHub Actions IAM role.
- A separate EC2 IAM role.
- Least-privilege ECR and SSM permissions.
- A restricted OIDC trust policy.
- `.env` only on EC2, not in Git.
- HTTPS through Nginx or an ALB for production.
- Restricted Security Group rules.

Avoid:

```text
AWS_ACCESS_KEY_ID in GitHub
AWS_SECRET_ACCESS_KEY in GitHub
MongoDB password in source code
SECRET_KEY in source code
.env committed to Git
```

## 25. Recommended Production Improvement — Immutable Tags

The current example uses:

```text
flask-student-app:latest
```

This is simple for learning and initial deployment, but production deployments should preferably use an immutable tag such as the Git commit SHA:

```text
flask-student-app:8f32c7a
```

Benefits:

- Every deployment is traceable.
- Rollback is easier.
- You know exactly which source revision is running.
- Avoids ambiguity around `latest`.

## 26. Complete Workflow Summary

```text
Developer
    |
    | git push origin main
    v
GitHub
    |
    v
GitHub Actions
    |
    +--> pytest
    |       |
    |       +--> FAIL -> STOP
    |       |
    |       +--> PASS
    |
    +--> GitHub OIDC
    |       |
    |       v
    |   AWS STS
    |       |
    |       v
    |   GitHubActions-Flask-ECR-Role
    |
    +--> docker build
    |
    +--> docker push
            |
            v
     Amazon ECR
            |
            | image
            v
     AWS Systems Manager
            |
            | SendCommand
            v
          EC2
            |
            +--> docker login
            +--> docker pull
            +--> docker stop
            +--> docker rm
            +--> docker run
                    |
                    v
             Flask container
                    |
                    v
               Port 5000
                    |
                    v
             /health endpoint
```

## 27. Final Result

The complete automated deployment is:

```text
Code change
    ↓
git push main
    ↓
GitHub Actions
    ↓
pytest
    ↓
Docker build
    ↓
GitHub OIDC
    ↓
AWS IAM
    ↓
Amazon ECR
    ↓
AWS SSM
    ↓
Amazon EC2
    ↓
Docker pull
    ↓
Docker run
    ↓
Flask application
```

A successful deployment means the application can be reached at:

```text
http://<EC2_PUBLIC_IP>:5000/
```

and the health endpoint is:

```text
http://<EC2_PUBLIC_IP>:5000/health
```
