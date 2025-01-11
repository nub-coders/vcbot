from aiortc import RTCPeerConnection, RTCConfiguration, RTCIceServer
import asyncio
import random

async def generate_dynamic_webrtc_params():
    # Configuration for ICE servers
    configuration = RTCConfiguration(
        iceServers=[RTCIceServer(urls=["stun:stun.l.google.com:19302"])]
    )
    
    pc = RTCPeerConnection(configuration=configuration)

    # Create a dummy data channel to initiate ICE gathering
    pc.createDataChannel("dummy")

    # Generate the SDP offer to gather ICE candidates
    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)

    # Wait for ICE gathering to complete
    while pc.iceGatheringState != "complete":
        await asyncio.sleep(0.1)

    # Extract ICE parameters and fingerprints from the SDP
    sdp = pc.localDescription.sdp
    ufrag, pwd = None, None
    fingerprints = []

    for line in sdp.splitlines():
        if line.startswith("a=ice-ufrag:"):
            ufrag = line.split(":")[1]
        elif line.startswith("a=ice-pwd:"):
            pwd = line.split(":")[1]
        elif line.startswith("a=fingerprint:"):
            _, fingerprint = line.split(" ", 1)
            fingerprints.append({
                "hash": "sha-256",
                "setup": "active",
                "fingerprint": fingerprint.replace(":", "").lower()
            })

    # Generate SSRC for RTP stream
    ssrc = random.randint(100000, 99999999)

    # Close the peer connection
    await pc.close()

    # Return the WebRTC parameters
    return {
        "ufrag": ufrag,
        "pwd": pwd,
        "fingerprints": fingerprints,
        "ssrc": ssrc
    }

# Generate WebRTC parameters
params = asyncio.run(generate_dynamic_webrtc_params())
print(params)
