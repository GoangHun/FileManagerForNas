# Synology API 연동 노트

이 문서는 AI 파일 관리 시스템을 개발하면서 Synology NAS API를 연동하는 과정에서 파악한 주요 정보와 트러블슈팅 경험을 정리한 것입니다.

## 1. 기본 정보

-   **API 엔트리포인트:** 모든 API 요청은 `[호스트 주소]/webapi/entry.cgi`를 통해 이루어집니다.
-   **요청 형식:** GET 또는 POST 요청을 사용하며, 요청 파라미터는 `api`, `version`, `method`를 기본적으로 포함합니다.

## 2. 인증 (`SYNO.API.Auth`)

-   **API 이름:** `SYNO.API.Auth`
-   **메서드:** `login`
-   **HTTP 동사:** `POST`
-   **파라미터 전달:** 로그인과 같이 민감한 정보를 포함하므로, 파라미터는 URL 쿼리 스트링(`params`)이 아닌, 요청 본문(body)에 `form-encoded` 형태(`data`)로 전달해야 합니다.
    -   `httpx` 라이브러리 사용 시 `client.post(..., data=params)` 형태로 호출해야 합니다. `params=params`로 호출하면 `101` 오류가 발생합니다.
-   **필수 파라미터:**
    -   `api`: `SYNO.API.Auth`
    -   `version`: `7` (또는 그 이상, `SYNO.API.Info`를 통해 확인 가능)
    -   `method`: `login`
    -   `account`: 사용자 이름
    -   `passwd`: 비밀번호
    -   `session`: 세션을 사용할 애플리케이션 이름 (예: `FileStation`)
    -   `format`: `sid` (세션 ID) 또는 `cookie`
-   **2단계 인증 (2FA/OTP):**
    -   사용자 계정에 2FA가 활성화된 경우, 로그인 요청 시 `otp_code` 파라미터를 추가로 보내야 합니다.
    -   `otp_code`가 누락되면 `403` 오류가 발생합니다.
-   **성공 응답:**
    -   `success: true`
    -   `data.sid`: 세션 ID. 이후의 모든 API 요청에 포함되어야 합니다.
    -   `data.synotoken`: CSRF(Cross-Site Request Forgery) 방지를 위한 토큰.

## 3. 세션 관리

로그인 성공 후의 모든 요청은 **인증된 세션**임을 증명해야 합니다.

1.  **세션 ID (`_sid`):**
    -   로그인 시 받은 `sid` 값입니다.
    -   각 API 요청의 URL 파라미터에 `_sid=[세션 ID]` 형태로 포함하여 보냅니다.
    -   `httpx`와 같은 최신 HTTP 클라이언트는 `Set-Cookie` 헤더를 통해 세션을 자동으로 관리하기도 하므로, URL 파라미터와 쿠키 방식 중 하나 또는 둘 다를 API가 요구할 수 있습니다.

2.  **CSRF 토큰 (`Syno-Token`):**
    -   로그인 시 받은 `synotoken` 값입니다.
    -   보안 강화를 위해 이후 모든 요청의 **HTTP 헤더**에 `X-SYNO-Token: [토큰 값]` 형태로 포함하여 보내야 합니다.
    -   이 헤더가 누락되면 `401` 또는 `119` 오류가 발생할 수 있습니다.

## 4. 파일/폴더 조회 (`SYNO.FileStation.List`)

-   **API 이름:** `SYNO.FileStation.List`
-   **루트 경로 접근:**
    -   API는 파일 시스템의 최상위 루트(`folder_path="/"`)에 대한 직접적인 조회를 허용하지 않는 것으로 보입니다. 이 경우 `403 Forbidden`과 유사한 권한 오류가 발생할 수 있습니다.
    -   최상위 수준의 폴더 목록을 얻기 위해서는 아래의 `list_share` 메서드를 사용해야 합니다.
-   **`list_share` 메서드:**
    -   **용도:** File Station에 설정된 모든 **공유 폴더(Shared Folder)** 목록을 가져옵니다.
    -   `method`: `list_share`
    -   애플리케이션의 초기 화면 구성 시 이 메서드를 호출하여 시작점을 만듭니다.
-   **`list` 메서드:**
    -   **용도:** 특정 공유 폴더 또는 그 하위 경로의 파일 및 폴더 목록을 가져옵니다.
    -   `method`: `list`
    -   **필수 파라미터:** `folder_path` (예: `/photo`, `/video/movies`)
    -   **추가 정보:** `additional` 파라미터에 `["real_path", "size", "time"]` 등을 추가하여 파일 크기, 수정 시간 등의 상세 정보를 함께 받을 수 있습니다.

## 5. 주요 오류 코드 정리

디버깅 과정에서 겪었던 주요 오류 코드와 그 원인은 다음과 같습니다.

-   `[SSL: WRONG_VERSION_NUMBER]`: **(클라이언트 오류)** HTTP를 사용하는 서버에 HTTPS로 연결을 시도할 때 발생.
-   `101: No such API, method or version`: **(클라이언트 오류)** API 요청 파라미터가 잘못되었을 경우. (예: POST 요청에 `data` 대신 `params` 사용)
-   `403: One time password authentication is required`: **(인증 오류)** 2FA가 활성화된 계정에 `otp_code` 없이 로그인을 시도할 때 발생.
-   `401: Invalid session ID` 또는 `119: Session timeout`: **(세션 오류)** 로그인 후 다른 API를 호출할 때 발생. `_sid`가 유효하지 않거나 `X-SYNO-Token` 헤더가 누락되었을 가능성이 높음.
-   `403 Forbidden` (`/api/files` 응답): **(권한 오류)** 코드 자체의 문제보다는, Synology NAS에 설정된 사용자 계정 권한 문제일 가능성이 높음.
    1.  `File Station` 애플리케이션 사용 권한이 없는 경우.
    2.  접근하려는 공유 폴더에 대한 읽기 권한이 없는 경우.
    3.  `folder_path=/` 와 같이 허용되지 않는 루트 경로 조회를 시도하는 경우.
