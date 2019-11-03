"""beepbeep discord bot. Licensed under MIT License."""

import asyncio
import discord
import youtube_dl
import os
import re
import ctypes
from datetime import datetime
from discord.ext import commands

#Load Opus
ctypes.util.find_library('libopus.so')
if discord.opus.is_loaded() is False:
    print('Opus did not load correctly')
elif discord.opus.is_loaded() is True:
    print('Opus loaded correctly')

#Currently Playing
currentPlaying = 'None'

#Get token
TOKEN = open('token.txt', 'r').read()
#TOKEN = tokenFile.strip()


#Totally stole this from stackoverflow
def removeSubstr(input_list, substr):
    """Remove substring for deletion of .webm files"""
    out_list = []
    for element in input_list:
        out_list.append(re.sub(substr, '_', element))
    return out_list

def bigTime():
    """Get time in H:M:S ||Y/M/Dformat."""
    _bigTime = datetime.strftime(datetime.now(), '%H:%M:%S||%y/%m/%d')
    return _bigTime


# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''


ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(title)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'  # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


class Cmds(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def play(self, ctx, *query):
        """Streams from a url/search"""

        global currentPlaying
        channel = ctx.author.voice.channel

        query = ' '.join(query)

        #Join channel if not already
        if ctx.voice_client.is_connected() is False:
            if ctx.voice_client is not None:
                return await ctx.voice_client.move_to(channel)
            await channel.connect()

        if ctx.voice_client.is_playing() is True:
            ctx.voice_client.stop()

        async with ctx.typing():
            player = await YTDLSource.from_url(query, loop=self.bot.loop, stream=False)
            ctx.voice_client.play(player, after=lambda e: print('Player error: %s' % e) if e else None)

        currentPlaying = 'Now playing: {}'.format(player.title)
        await ctx.send(':radio: Now playing: ' + currentPlaying)
        print('Playing: {0} || {1}'.format(currentPlaying, bigTime()))

        #Removes downloaded videofile
        removeFile = ''.join(removeSubstr([player.title], ' '))
        await asyncio.sleep(20)
        if os.path.isfile(removeFile):
            os.remove(removeFile)

    @commands.command()
    async def pause(self, ctx):
        """Pause/Unpause audio stream."""

        if ctx.voice_client.is_paused() is False:
            ctx.voice_client.pause()
            await ctx.send(':pause_button: Paused')
            print('Paused || {}'.format(bigTime()))

        elif ctx.voice_client.is_paused() is True:
            ctx.voice_client.resume()
            await ctx.send(':arrow_forward: Unpaused')
            print('Unpaused || {}'.format(bigTime()))

    @commands.command()
    async def stop(self, ctx):
        """Stop and disconnect the bot from voice."""
        global currentPlaying
        currentPlaying = 'None'
        await ctx.voice_client.disconnect()
        await ctx.send(':stop_button: Stopped')
        print('Left voice || {}'.format(bigTime()))

    @commands.command()
    async def list(self, ctx):
        """List the current song."""
        if currentPlaying is not 'None':
            await ctx.send(':cd: Currently playing: ' + currentPlaying)
        else:
            await ctx.send(':red_circle: Nothing is playing :red_circle:')

    @commands.command()
    async def volume(self, ctx, volume: int):
        """Change the player's volume."""
        if ctx.voice_client is None:
            return await ctx.send(':red_circle: Not connected to a voice channel :red_circle:')

        ctx.voice_client.source.volume = volume / 100
        await ctx.send(":sound: Changed volume to {}%".format(volume))

    @commands.command()
    async def clean(self, ctx):
        #List that will hold to-be-deleted messages
        deleteQueue = []

        #Get datetime object that is 14 days old for after= limiter in ctx.history
        """TODO:
                Make it so instead of just not erroring out,
                move back the month as well as the day, so it is
                always 14 days back (the maximum age of a message
                that can be deleted)."""
        oldYear = datetime.strftime(datetime.now(), '%Y')
        oldMonth = datetime.strftime(datetime.now(), '%m')

        #Day requires special fixing so it doesn't go into the negatives
        oldDay = int(datetime.strftime(datetime.now(), '%d')) - 14
        if oldDay < 1:
            oldDay = 1
        oldDay = str(oldDay)

        oldTime = '{0}/{1}/{2}'.format(oldYear, oldMonth, oldDay)
        oldTime = datetime.strptime(oldTime, '%Y/%m/%d')

        #Get the last 100 messages from the past 14 days and loop through them
        async for message in ctx.history(limit=100, after=oldTime):
            msgSplit = list(message.content)
            #Make sure message is not empty
            if len(msgSplit) != 0:
                #Add bot's messages to delete queue
                if bot.user == message.author:
                    deleteQueue.append(message)
                #Add user commands to delete queue
                elif 'b' is msgSplit[0] and '/' is msgSplit[1]:
                    deleteQueue.append(message)

        #Delete messages and print to console
        await ctx.channel.delete_messages(deleteQueue)
        print('Deleted {0} messages in {1}/{2} || {3}'.format(
                                                              len(deleteQueue),
                                                              ctx.guild,
                                                              ctx.channel,
                                                              bigTime()))

    @commands.command(name='help')
    async def _help(self, ctx):
        """List commands."""
        await ctx.send(""":question: Beepbeep commands:
        b/play <url> - Plays a YouTube URL/Searches for song.
        b/pause - Pause/Unpause.
        b/stop - Disconnects the bot.
        b/list - List the current song.
        b/volume <volume> - Changes volume.
        b/clean - Remove bot's messages and any user's commands.
        b/help - This command.
        """)

    @play.before_invoke
    async def ensure_voice(self, ctx):
        """Make sure bot is connected to a voice channel.

        To get going I stole the `basic_voice.py` example from
        the offical discord.py repo, and this is left over. I'm going
        to keep it for now since it can't hurt anything."""
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("Error: Author not connected to voice channel")
                raise commands.CommandError("Author not connected to a voice channel.")
        elif ctx.voice_client.is_playing():
            ctx.voice_client.stop()


#Init bot
bot = commands.Bot(command_prefix=commands.when_mentioned_or("b/"))


@bot.event
async def on_ready():
    #Logged in
    print('Logged in as {0} ({0.id}) || {1}'.format(bot.user, bigTime()))
    print('------')

    game = discord.Game("Use b/help")
    await bot.change_presence(status=discord.Status.online, activity=game)

bot.remove_command('help')
bot.add_cog(Cmds(bot))
bot.run(TOKEN.strip())
