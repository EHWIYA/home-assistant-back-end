"""실제 GitHub OIDC 교환을 확인한다. JWT·access token은 출력/저장하지 않는다."""
import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request


def identity(audience):
    url = os.environ['ACTIONS_ID_TOKEN_REQUEST_URL']
    separator = '&' if '?' in url else '?'
    request = urllib.request.Request(
        url + separator + urllib.parse.urlencode({'audience': audience}),
        headers={'Authorization': 'Bearer ' + os.environ['ACTIONS_ID_TOKEN_REQUEST_TOKEN']},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)['value']


def exchange(client_id, jwt):
    request = urllib.request.Request(
        'https://api.tailscale.com/api/v2/oauth/token-exchange',
        data=urllib.parse.urlencode({'client_id': client_id, 'jwt': jwt}).encode(),
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.load(response)
            assert data.get('access_token'), 'No Tailscale access token'
            return response.status
    except urllib.error.HTTPError as error:
        # 오류 응답 본문에는 인증 진단 링크가 포함될 수 있어 출력하지 않는다.
        error.close()
        return error.code


def main():
    client_id = os.environ['TS_OIDC_CLIENT_ID']
    audience = os.environ['TS_OIDC_AUDIENCE']
    assert client_id and audience, 'OIDC repository variables missing'
    jwt = identity(audience)
    part = jwt.split('.')[1]
    claims = json.loads(base64.urlsafe_b64decode(part + '=' * (-len(part) % 4)))
    expected = {
        'iss': 'https://token.actions.githubusercontent.com',
        'sub': 'repo:EHWIYA/home-assistant-back-end:ref:refs/heads/main',
        'aud': audience,
        'repository_id': '1243116171',
        'repository_owner_id': '150232499',
        'workflow_ref': 'EHWIYA/home-assistant-back-end/.github/workflows/deploy.yml@refs/heads/main',
        'ref': 'refs/heads/main',
    }
    assert all(claims.get(key) == value for key, value in expected.items()), 'OIDC claims mismatch'
    denied = exchange(client_id, identity(audience + '/invalid-audience-probe'))
    assert denied in (400, 401, 403), 'Wrong audience was not rejected'
    # 정상 교환을 마지막에 하여 의도한 거부 진단이 현재 오류로 남지 않게 한다.
    accepted = exchange(client_id, jwt)
    assert accepted == 200, 'Authorized OIDC token exchange failed'
    print(json.dumps({'identity_claims_match': True, 'wrong_audience_http': denied,
                      'authorized_exchange_http': accepted, 'tokens_saved': False}))


if __name__ == '__main__':
    main()
