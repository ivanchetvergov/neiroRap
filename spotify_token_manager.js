require('dotenv').config();
const https = require("https");
const querystring = require("querystring");
const fs = require("fs");
const path = require("path");

const client_id = process.env.SPOTIFY_CLIENT_ID;
const client_secret = process.env.SPOTIFY_CLIENT_SECRET;
const refresh_token = process.env.SPOTIFY_REFRESH_TOKEN;
const redirect_uri = process.env.SPOTIFY_REDIRECT_URI;

// Функция для обновления access токена
function refreshAccessToken() {
  return new Promise((resolve, reject) => {

    // В потоке Refresh Token Flow нужны только refresh_token, client_id и client_secret.
    // redirect_uri здесь не требуется, но передадим на всякий случай, если это
    // общая функция для разных грантов.
    const postData = querystring.stringify({
      grant_type: "refresh_token",
      refresh_token: refresh_token,
      client_id: client_id,
      client_secret: client_secret,
      // redirect_uri: redirect_uri // <- Можно закомментировать для потока обновления
    });

    const options = {
      // 🚨 ИСПРАВЛЕНО: hostname должен быть настоящим адресом, без протокола
      hostname: "accounts.spotify.com",
      path: "/api/token",
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "Content-Length": Buffer.byteLength(postData),
      },
    };

    const req = https.request(options, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => {
        try {
          const response = JSON.parse(data);
          if (response.access_token) {
            resolve(response.access_token);
          } else {
            reject(new Error("No access token in response: " + data));
          }
        } catch (err) {
          reject(err);
        }
      });
    });

    req.on("error", reject);
    req.write(postData);
    req.end();
  });
}

// Функция для обновления .env файла
function updateEnvFile(newToken) {
  const envPath = path.join(__dirname, ".env");
  let envContent = fs.readFileSync(envPath, "utf8");

  // Заменяем значение SPOTIFY_ACESS_TOKEN
  const regex = /SPOTIFY_ACCESS_TOKEN="[^"]*"/;

  if (regex.test(envContent)) {
    envContent = envContent.replace(regex, `SPOTIFY_ACCESS_TOKEN="${newToken}"`);
  } else {
    // Если строка не найдена, добавляем её
    envContent += `\nSPOTIFY_ACCESS_TOKEN="${newToken}"`;
  }

  fs.writeFileSync(envPath, envContent, "utf8");
  console.log(".env файл обновлён с новым токеном");
}

// Основная функция
async function main() {

  if (!client_id || !client_secret || !refresh_token) {
    console.error("Ошибка: Проверьте, что SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET и SPOTIFY_REFRESH_TOKEN установлены в .env файле.");
    process.exit(1);
  }

  console.log("Обновление Spotify access token...");

  try {
    const newAccessToken = await refreshAccessToken();
    console.log("Новый access token получен:", newAccessToken.substring(0, 20) + "...");

    updateEnvFile(newAccessToken);
    console.log("\nТокен сохранён в .env файл");
    console.log("Готово! Можете использовать обновлённый токен");

    return newAccessToken;
  } catch (error) {
    console.error("Ошибка при обновлении токена:", error.message);
    process.exit(1);
  }
}

// Если скрипт запущен напрямую
if (require.main === module) {
  main();
}

// Экспортируем для использования в других модулях
module.exports = { refreshAccessToken, updateEnvFile, main };