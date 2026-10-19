# 클라우드 확장 계획

현재 AWS 리소스, 컨테이너 이미지, 배포용 자격증명과 실제 추론 API는 생성하지 않았습니다. 비용은 산정 전입니다.

## 최소 배포안

```text
고정 모델 파일·매니페스트 → S3 private bucket
FastAPI 추론 코드 → Docker image → ECR
ECS Fargate CPU task → health check / model-info / predict
실행 로그·지연시간·오류 → CloudWatch
```

AWS 공식 문서는 Fargate를 EC2 호스트 관리 없이 컨테이너를 실행하는 방식으로 설명합니다. 이 프로젝트에서는 **CPU 추론 서비스**에 사용하고, GPU 학습은 별도 환경에서 다룹니다. [AWS Fargate 공식 문서](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html)

S3는 데이터·모델 해시와 함께 사용합니다. Versioning은 명시적으로 활성화해야 하며 버전 저장·운영 비용도 확인합니다. [S3 Versioning](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html)

## 구현 후 검증

1. 로컬/컨테이너/클라우드의 같은 입력에 대한 같은 모델 출력 확인.
2. 모델 해시·학습 데이터 release·라벨 정의·코호트가 model-info와 일치하는지 확인.
3. 프로세스 재시작 후 모델 로딩, 유효하지 않은 SMILES·입력 크기·실패 처리 확인.
4. 요청 수·p50/p95 지연·실패율 기록. 측정 조건과 표본 수 명시.
5. 요청 범위·예산·운영 기간을 결정한 뒤 리소스 생성. 유휴 리소스 종료와 정리 절차 기록.
6. 서비스 역할 최소 권한, API 키는 저장소에 넣지 않고 배포 환경의 secret 기능 사용.

MLflow 서버의 클라우드 상시 운영은 초기 범위에 포함하지 않습니다. 로컬 실험 추적 후 필요성이 생기면 확대합니다. [MLflow Tracking](https://mlflow.org/docs/latest/ml/tracking/)
