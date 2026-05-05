<?php
/**
 * Proxy CORS para aerobiologia.cat
 * Coloca este archivo junto a index.html en tu servidor.
 * El navegador llama a /proxy.php?target=forecast|api
 * y este script hace la petición al servidor de la UAB sin restricciones CORS.
 */
header('Access-Control-Allow-Origin: *');
header('Cache-Control: public, max-age=3600');

$targets = [
    'forecast' => 'https://aerobiologia.cat/pia/es/forecast/balears',
    'api'      => 'https://aerobiologia.cat/api/v0/forecast/balears/es/xml',
];

$key = isset($_GET['target']) && isset($targets[$_GET['target']])
     ? $_GET['target'] : 'forecast';

$url = $targets[$key];

$ctx = stream_context_create([
    'http' => [
        'method'          => 'GET',
        'timeout'         => 12,
        'follow_location' => 1,
        'header'          => implode("\r\n", [
            'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language: ca,es;q=0.9,en;q=0.8',
            'Referer: https://aerobiologia.cat/',
        ]),
    ],
    'ssl' => ['verify_peer' => true],
]);

$result = @file_get_contents($url, false, $ctx);

if ($result === false) {
    http_response_code(502);
    header('Content-Type: application/json');
    echo json_encode(['error' => "No se pudo conectar con $url"]);
    exit;
}

// Detect content type from response headers
$ct = 'text/html; charset=utf-8';
foreach ((array)($http_response_header ?? []) as $h) {
    if (stripos($h, 'content-type:') === 0) {
        $ct = trim(substr($h, strlen('content-type:')));
    }
}
header("Content-Type: $ct");
echo $result;
