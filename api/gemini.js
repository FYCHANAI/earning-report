export default async function handler(req, res) {
    // 1. 確保只接受 POST 請求
    if (req.method !== 'POST') {
        return res.status(405).json({ error: 'Method Not Allowed' });
    }

    // 2. 接收前端傳來的資料
    const { prompt, systemInstruction } = req.body;
    
    // 3. 讀取 Vercel 後台的環境變數 (金鑰安全藏在這裡)
    const API_KEY = process.env.GEMINI_API_KEY;

    if (!API_KEY) {
        return res.status(500).json({ error: '伺服器缺少 API 金鑰設定，請至 Vercel 後台檢查。' });
    }

    const fullPrompt = `${systemInstruction}\n\n用戶的請求是：${prompt}`;
    
    // 🚨 終極確認：這是最標準的穩定版模型，絕對沒有 -latest 後綴
    const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${API_KEY}`;

    try {
        // 4. 向 Google 發送請求
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ contents: [{ parts: [{ text: fullPrompt }] }] })
        });

        const data = await response.json();
        
        if (!response.ok) {
            return res.status(response.status).json({ error: data.error?.message || 'Google API 發生錯誤' });
        }

        // 5. 成功後回傳給前端
        res.status(200).json(data);

    } catch (error) {
        res.status(500).json({ error: error.message });
    }
}
