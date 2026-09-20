# Deployment configuration

## Nginx HTTPS 적용 순서

`deploy/nginx.conf`는 Let's Encrypt 인증서 파일 경로를 사용합니다.

새 서버에서는 인증서 파일이 먼저 존재해야 하므로, 아래 순서대로 적용합니다.

1. nginx 설치 및 HTTP 서버 구성
2. Certbot 설치

```bash
sudo apt update
sudo apt install -y certbot python3-certbot-nginx
```

3. 인증서 발급

```bash
sudo certbot --nginx -d cody-chatbot.koreacentral.cloudapp.azure.com
```

4. `deploy/nginx.conf`를 nginx 설정에 적용
5. nginx 설정 검사

```bash
sudo nginx -t
```

6. nginx reload

```bash
sudo systemctl reload nginx
```

## HTTPS 동작 확인

443 포트가 nginx에서 열렸는지 확인합니다.

```bash
sudo ss -tlnp | grep ':443'
```

HTTPS `/health` 엔드포인트가 정상 응답하는지 확인합니다.

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://cody-chatbot.koreacentral.cloudapp.azure.com/health
```

`200`이 출력되면 정상입니다.

## 인증서 자동 갱신 확인

Certbot 자동 갱신 타이머 상태를 확인합니다.

```bash
sudo systemctl status certbot.timer --no-pager
```

갱신 과정을 실제 인증서 변경 없이 테스트합니다.

```bash
sudo certbot renew --dry-run
```

`Congratulations, all simulated renewals succeeded`가 출력되면 정상입니다.

## 주의사항

- 실제 인증서 파일은 GitHub 저장소에 올리지 않습니다.
- `deploy/nginx.conf`에는 인증서 파일의 경로만 포함합니다.
- 새 서버에서 `deploy/nginx.conf`를 먼저 적용하면 인증서 파일이 없어 nginx가 기동하지 않을 수 있습니다.
- 반드시 Certbot으로 인증서를 먼저 발급한 뒤 nginx 설정을 적용합니다.
