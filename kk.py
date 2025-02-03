from pyrogram import Client
from ntgcalls import NTgCalls, MediaDescription
import asyncio
from pyrogram.raw import functions, types

async def main():
        app = Client(
        "user",  # name doesn't matter since we're using session string
        api_id=21869707,
        api_hash='31ec80a4adad7aaad9262e894e3654e6',
        session_string='BQFNtIsAM19plldIgoeT3Hh2L7nX-UpEdV6cCvafkrE_dTM_PDA9kKJniZr4evzwNkmgPIxEdekXBi6_TA4kmJOAq8PbbTYQ-uS7uShIMpMaKSvD-Zou-BRps0PJcxiHadOixLKmXXUGRNSq45q00C4uVOK2FOxAwaOEiXJadggTaLZKqIg0FpC9KYEbuLL7U_bH1elalt6M-UhnbjzKn1qw8IijHhHsXCmYboIZtN7ExtdaJ8S01srDcNNsRVs1A1mfEPESdqH6W3F1a1m4ag1bcOabK2efRUhNjfJ3h5lyrRVoO_F_xDq2kqkdPHleg99ELjrGKEKFlVxEDgL6QMun4dMlYAAAAAHn-CaXAA',
        in_memory=True
    )
    
        calls = NTgCalls()
    
        await app.start()
    
        # Get the target chat
        chat = await app.get_chat("nub_coder_s")
        
        # Get full chat to get group call
        full_chat = await app.invoke(
            functions.channels.GetFullChannel(
                channel=await app.resolve_peer(chat.id)
            )
        )
        
        # Get group call from full chat
        group_call = full_chat.full_chat.call
        
        # Create media description
        media = MediaDescription(None
        )
        
        # Create call with group call from full chat
        call = await calls.create_call(
            chat_id=chat.id,
            media=media,
        )
        
        # Join group call
        await app.invoke(
            functions.phone.JoinGroupCall(
                call=group_call,
                join_as= await app.resolve_peer(app.me.id)
,
                params=call
            )
        )
        
        print("Successfully joined voice chat!")
        
        await asyncio.sleep(150)
        
        # Leave group call
        await app.invoke(
            functions.phone.LeaveGroupCall(
                call=group_call,
                source=0
            )
        )
        print("Left voice chat!")
        
    #except Exception as e:
     #   print(f"Error occurred: {str(e)}")
    
        await app.stop()

from pyrogram.raw.types import InputPeerSelf
from pyrogram import Client, types
asyncio.get_event_loop().run_until_complete(main())
