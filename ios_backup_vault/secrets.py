"""GCS 자격증명 해석. ADC 우선(우리가 비밀 저장 안 함). 선택적 keyring 저장소(argv 미노출)."""
import json


def _keyring_get(account):
    try:
        import keyring
    except ImportError:
        return None
    return keyring.get_password("ios-backup-vault", account)


def _keyring_set(account, value):
    import keyring  # 미설치면 ImportError → 호출측에서 안내
    keyring.set_password("ios-backup-vault", account, value)


def _creds_from_info(info):
    from google.oauth2 import service_account
    return service_account.Credentials.from_service_account_info(info)


def resolve_credentials(cfg):
    """cfg={"auth":"adc"|"keyring","account":...} → google credentials 또는 None(ADC)."""
    auth = (cfg or {}).get("auth", "adc")
    if auth == "adc":
        return None
    if auth == "keyring":
        raw = _keyring_get(cfg.get("account", "gcs"))
        if not raw:
            raise RuntimeError("keyring에 자격증명 없음. cloud-config 재실행 또는 ADC 사용.")
        return _creds_from_info(json.loads(raw))
    raise RuntimeError("알 수 없는 인증 방식입니다(adc 또는 keyring).")


def store_key_via_keyring(account, json_str):
    json.loads(json_str)  # 유효성
    _keyring_set(account, json_str)
