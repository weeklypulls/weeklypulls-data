def test_mupulls(live_server, requests_client):
    # create a MU-enabled pull-list
    data = {
        'title': 'test mu',
        'mu_enabled': True
    }
    response = requests_client.post(f'{live_server.url}/pull-lists/',
                                    json=data,
                                    )
    assert response.status_code == 201
    result = response.json()
    assert result['title'] == data['title']

    # check it's returned in view
    response = requests_client.get(f'{live_server.url}/pull-lists/')
    assert response.status_code == 200
    result = response.json()
    assert result[0]['title'] == data['title']

    # create a MUPull
    pl_id = result[0]['id']
    pull_1 = {'pull_list_id': pl_id,
              'series_id': 23012}
    response = requests_client.post(f'{live_server.url}/mupulls/',
                                    json=pull_1)
    assert response.status_code == 201
    result = response.json()
    assert result['pull_list_id'] == pull_1['pull_list_id']
    assert result['series_id'] == pull_1['series_id']

    # do it again
    pull_2 = {'pull_list_id': pl_id,
              'series_id': 23013}
    response = requests_client.post(f'{live_server.url}/mupulls/',
                                    json=pull_2)
    assert response.status_code == 201

    # check they are returned in view
    response = requests_client.get(f'{live_server.url}/mupulls/')
    assert response.status_code == 200
    result = response.json()
    assert len(result) == 2

    # purge the IDs so we can compare straight
    for d in result: d.pop('id')
    assert pull_1 in result
    assert pull_2 in result
