# QR Login Flow Implementation

## 1. Website Login Page
```javascript
// 1. Initialize QR Login
async function initializeQRLogin() {
  const response = await fetch('/auth/qr-login-init', {
    method: 'POST'
  });
  const { session_id } = await response.json();
  
  // Generate QR code with session_id
  // Using any QR library like qrcode.js
  generateQRCode(session_id);
  
  // Connect to WebSocket to wait for mobile login
  const ws = new WebSocket(`ws://your-server/ws/login/${session_id}`);
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.event === 'login_success') {
      // Store the token and redirect
      localStorage.setItem('token', data.token);
      window.location.href = '/dashboard';
    }
  };
}
```

## 2. Mobile App QR Scanner
```javascript
// When QR code is scanned
async function handleQRScan(session_id) {
  const response = await fetch('/auth/qr-login-complete', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${your_existing_token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      session_id: session_id
    })
  });
  
  const result = await response.json();
  if (result.status === 'success') {
    // Show success message
  }
}
```

# Player-to-Player Interaction

## 1. Generate Personal QR Code
```javascript
function generatePersonalQR(player_id, latitude, longitude) {
  const data = {
    type: 'player_interaction',
    player_id: player_id,
    latitude: latitude,
    longitude: longitude,
    timestamp: Date.now()
  };
  
  // Generate QR code with this data
  return generateQRCode(JSON.stringify(data));
}
```

## 2. Scan Other Player's Code
```javascript
async function scanPlayerQR(qrData) {
  const data = JSON.parse(qrData);
  
  // Verify we're in proximity
  const currentPosition = await getCurrentPosition();
  
  const response = await fetch('/qr/scan', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${your_token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      player_id: your_player_id,
      qr_code: data.player_id,
      latitude: currentPosition.latitude,
      longitude: currentPosition.longitude
    })
  });
  
  const result = await response.json();
  handleScanResult(result);
}
```

## 3. Handle Real-time Updates
```javascript
function connectToPlayerUpdates(player_id) {
  const ws = new WebSocket(`ws://your-server/ws/player/${player_id}`);
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    switch(data.event) {
      case 'player_interaction':
        handlePlayerInteraction(data);
        break;
      case 'qr_scan':
        handleQRScan(data);
        break;
    }
  };
  
  ws.onclose = () => {
    // Implement reconnection logic
    setTimeout(() => connectToPlayerUpdates(player_id), 1000);
  };
}

function handlePlayerInteraction(data) {
  if (data.success) {
    // Update UI to show successful interaction
    showInteractionSuccess(data.message);
  } else {
    // Show error message
    showInteractionError(data.message);
  }
}
```
