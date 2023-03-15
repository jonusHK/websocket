from starlette import status


async def test_회원가입(db_setup, redis_handler, client):
    email = 'test_signup@test.com'
    response = await client.post('/users/signup', json={
       'name': 'test_signup',
       'mobile': '01011111111',
       'email': email,
       'password': 'test_signup'
    })
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()['data']['uid'] == email
