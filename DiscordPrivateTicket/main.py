"""A bot to list all members of a server as well as make ticket channels"""
import csv
import sys
import time
import re
import discord
import datetime
import asyncio
import requests
import os
import threading
import platform
import sqlite3
from discord.ext import commands
from discord import Message

if platform.system() == "Windows":
    from win32com.client import Dispatch
from electrum import bitcoin
from electrum import keystore

# Global Constants
token = ''
command_prefix = '-'
bot_name = "PrivTicket Bot"
seeds = {}
bot = None
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
conn = None
c = None


# Create files and directories
def generate_database():
    global conn, c
    if not os.path.isdir('database/'):
        os.mkdir('database/')
    if not os.path.isfile('database/data.db'):
        conn = sqlite3.connect('database/data.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE servers
                     (serverid TEXT, servername TEXT, prefix TEXT, ticketnumber INT, intro TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS Addresses 
        (serverid TEXT, address TEXT, balance REAL, ticket INT)''')
        c.execute(
            '''CREATE TABLE IF NOT EXISTS tickets(serverid TEXT NOT NULL, channelid TEXT NOT NULL, messageid TEXT, 
            userid TEXT NOT NULL, ticket INT NOT NULL, username TEXT, content TEXT, address TEXT, requiredbtc REAL, 
            dollaramnt REAL, senttime TEXT, paymentattempt INT  DEFAULT (0));''')
        conn.commit()
    else:
        conn = sqlite3.connect('database/data.db')
        c = conn.cursor()


def get_constants():
    global token, command_prefix, bot_name
    with open('settings/settings.txt') as fp:
        line = fp.readline()
        while line:
            if line[0] is not '' and line[0] is not '#':
                split = line.strip().rstrip('\n').split('=', 1)
                if split[0] == 'token':
                    token = split[1]
                elif split[0] == 'prefix':
                    command_prefix = split[1]
                elif split[0] == 'bot_name':
                    bot_name = split[1]
                elif split[0] == 'add_to_startup':
                    if split[1].lower().strip() == 'true':
                        add_to_startup()
            line = fp.readline()
        fp.seek(0)
    if len(token) < 14:
        input('Please follow TO GET A token directions in README.txt to get a token')
        sys.exit(0)


def generate_settings_file():
    if not os.path.isdir('settings/'):
        os.mkdir('settings/')
    if not os.path.isfile('settings/settings.txt'):
        conf_create = open("settings/settings.txt", "w+")
        command_prefix_input = input('What would you like your prefix to be? Leave blank for default. ')
        while (command_prefix_input.isalpha() and len(command_prefix_input) == 1) or command_prefix_input.isdigit() or 1 > len(command_prefix_input) > 4:
            print("That prefix is too dangerous.")
            command_prefix_input = input('What would you like your prefix to be? Leave blank for default. ')
        token_input = input('What is your token? (Check README.txt): ')
        while not re.search("[MN][A-Za-z\d]{23}\.[\w-]{6}\.[\w-]{27}", token_input):
            print("That token seems invalid. You can place it manually in the settings.txt if you think otherwise.")
            token_input = input('What is your token? ')
        bot_name_input = input('What do you want your bot to be called? (Blank for default): ')
        while not re.search("^(.+?){2,32}", bot_name_input):
            if bot_name_input == '':
                bot_name_input = "PrivTicket Bot"
            else:
                bot_name_input = input('Please try a valid name.\nWhat do you want your bot to be called?: ')
        startup_input = input('What do you want your bot to be called? (Y/y): ')
        if startup_input.lower().strip() == 'y':
            startup_input = 'true'
        conf_create.write('#Your bot token. Please follow TO GET A token directions in README.txt to get a '
                          'token\ntoken=' + token_input + '\n#Your bot prefix\nprefix=' + command_prefix_input + '\n#Your bot name\nbot_name=' + bot_name_input + '\n#Add to startup(true/false)\nadd_to_startup=' + startup_input)
        conf_create.close()


def add_to_startup():
    if platform.system() == "Windows":
        user_name = os.getenv('username')
        startup_directory = 'C:\\Users\\' + user_name + '\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\\'
        if not os.path.isfile(startup_directory + 'mclient.ink'):
            path = os.path.join(startup_directory, "mclient.lnk")
            target = os.getcwd() + "\\main.py"
            working_dir = os.getcwd()
            icon = os.getcwd() + "\\settings\\tbot.ico"
            shell = Dispatch('WScript.Shell')
            shortcut = shell.CreateShortCut(path)
            shortcut.Targetpath = target
            shortcut.WorkingDirectory = working_dir
            shortcut.IconLocation = icon
            shortcut.save()


class PrivBot(commands.Bot):
    async def on_ready(self):
        print('Logged in as')
        print(self.user.name + ' displayed as ' + bot_name)
        print(self.user.id)
        print("Prefix: " + command_prefix)
        print('------')
        print('Ready to work')
        for server in self.guilds:
            for channel in server.channels:
                if channel.name == 'general':
                    pass
                    # msg = await channel.send("Hello there")
            c.execute('''SELECT serverid FROM servers WHERE serverid=?''', (server.id,))
            got = c.fetchone()
            if got is None:
                c.execute('''INSERT INTO servers(servername, serverid, prefix, ticketnumber, intro)
                                      VALUES(?,?,?,?,?)''', (server.name, server.id, '-', 0, None))
            c.execute('''CREATE TABLE IF NOT EXISTS Addresses (serverid TEXT, 
            address TEXT, balance REAL, ticket INT)''')
            conn.commit()
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name='you heathens writhe'))
        await self.user.edit(username=bot_name)
        threading.Timer(10, check_payments).start()

    async def on_server_join(self, server):
        c.execute('''INSERT INTO servers(servername, serverid, prefix, ticketnumber, intro)
                                          VALUES(?,?,?,?,?)''', (server.name, server.id, '-', 0, None))
        conn.commit()

    async def on_command_error(self, error, ctx):
        print("Error on: ")
        print(ctx)
        if isinstance(error, commands.CommandNotFound):
            return
        else:
            print(error)

    async def on_message(self, ctx):
        if ctx.channel.name == 'tickets' and not ctx.content == command_prefix + 'ticket':
            await ctx.author.send("You may only post " + command_prefix + 'ticket in the ticket channel')
            await Message.delete(ctx)
        else:
            await self.process_commands(ctx)


bot = PrivBot(command_prefix=command_prefix)


@bot.command(pass_context=True)
async def ticket(ctx):
    """Opens up a new ticket channel"""
    if ctx.message.channel.name == "tickets":
        await Message.delete(ctx.message)
        server = ctx.guild
        server_id = server.id
        author_id = ctx.author.id
        author_name = ctx.message.author.display_name
        c.execute('''SELECT ticketnumber FROM servers WHERE serverid=?''', (server_id,))
        number = c.fetchone()[0]
        c.execute('''SELECT intro FROM servers WHERE serverid=?''', (server_id,))
        server_intro = c.fetchone()[0]
        overwrites = {
            server.default_role: discord.PermissionOverwrite(read_messages=False),
            server.me: discord.PermissionOverwrite(read_messages=True)
        }
        test = await ctx.message.guild.create_text_channel(name=str(number), overwrites=overwrites)
        if server_intro is not None:
            try:
                await test.send("Hello. Please copy, paste and fill out the following form.\n"
                                + "```" + command_prefix + "send " + server_intro + "```")
            except:
                print("I couldn't send the intro to channel, sending to author")
                await ctx.message.author.send(
                    "Hello. Please copy, paste and fill out the following form in the ticket\n"
                    + "```" + command_prefix + "send " + server_intro + "```")
        c.execute('''UPDATE servers SET ticketnumber = ? WHERE serverid=? ''', (str(number + 1), server.id,))
        cleaned_name = re.sub("[^0-9a-zA-Z# '.!?]+", '', author_name)
        query = '''INSERT INTO tickets (serverid, ticket, channelid, userid, username)
                                      VALUES(?,?,?,?,?)'''
        c.execute(query, (str(server_id), str(number), str(test.id), str(author_id), cleaned_name,))
        conn.commit()
    else:
        await ctx.message.author.send("Please use the correct channel labeled 'tickets'")


@bot.command(pass_context=True)
async def intro(ctx):
    """Adds/ updates the ticket channel welcome message"""
    if ctx.message.author.guild_permissions.administrator:
        message_content = ctx.message.content[len(command_prefix) + 6:]
        c.execute('''UPDATE servers SET intro = ? WHERE serverid = ? ''',
                  (message_content, ctx.message.guild.id,))
        conn.commit()
        await ctx.send("Updated.")
    await Message.delete(ctx.message)


@bot.command(pass_context=True)
async def prefix(ctx):
    """Changes the prefix to enact the bot"""
    if ctx.message.author.guild_permissions.administrator:
        new_prefix = (ctx.message.content[len(command_prefix) + 7:])
        server_id = ctx.message.guild.id
        if (new_prefix.isalpha() and len(new_prefix) == 1) or new_prefix.isdigit():
            await ctx.message.channel.send("That prefix is too dangerous. Please choose another.")
        else:
            c.execute('''UPDATE servers SET ticketnumber = ? WHERE serverid = ? ''', (new_prefix, server_id,))
            conn.commit()
            await ctx.message.channel.send("My future prefix will be: " + new_prefix)
    else:
        await ctx.send("You do not have permissions for that.")
    await Message.delete(ctx.message)


@bot.command(pass_context=True)
async def send(ctx):
    """Stores local copy of ticket data. Can also append new data to an old ticket"""
    await Message.delete(ctx.message)
    server = ctx.message.guild
    query = '''SELECT content FROM tickets WHERE channelid = ? and serverid = ?'''
    c.execute(query, (ctx.message.channel.id, ctx.message.guild.id))
    old_content = c.fetchone()
    if old_content is None:
        await ctx.send("Channel is not in my database.")
        return
    else:
        if old_content[0] is not None:
            new_content = old_content[0] + "Update at: " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n" \
                          + ctx.message.content[len(command_prefix) + 5:] + "\n"
        else:
            new_content = ctx.message.content[len(command_prefix) + 5:] + '\n'
        query = '''UPDATE tickets SET content = ? WHERE channelid = ? and serverid = ?'''
        c.execute(query, (new_content, ctx.message.channel.id, ctx.message.guild.id,))
        conn.commit()
        await ctx.send(ctx.message.author.display_name + " I have received your message.")


@bot.command(pass_context=True)
async def close(ctx):
    """Deletes the channel and local ticket data"""
    if ctx.message.author.guild_permissions.administrator:
        server = ctx.message.guild
        query = '''SELECT userid FROM tickets WHERE channelid = ? and serverid = ?'''
        c.execute(query, (ctx.message.channel.id, ctx.message.guild.id,))
        check_exist = c.fetchone()
        if check_exist is not None:
            query = '''DELETE FROM tickets WHERE channelid = ? and serverid = ?'''
            c.execute(query, (ctx.message.channel.id, ctx.message.guild.id,))
            conn.commit()
            await discord.TextChannel.delete(ctx.message.channel)
        else:
            await ctx.send("Channel not in database.")
            await Message.delete(ctx.message)


@bot.command(pass_context=True)
async def console(ctx):
    """Posts ticket data to the local console"""
    if ctx.message.author.guild_permissions.administrator:
        await Message.delete(ctx.message)
        query = '''SELECT content FROM tickets WHERE channelid = ? and serverid = ?'''
        c.execute(query, (ctx.message.channel.id, ctx.message.guild.id,))
        check_exist = c.fetchone()
        if check_exist is not None:
            print(check_exist[0])
        else:
            print("No data")


@bot.command(pass_context=True)
async def post(ctx):
    """Posts ticket data to the channel"""
    if ctx.message.author.guild_permissions.administrator:
        await Message.delete(ctx.message)
        query = '''SELECT content FROM tickets WHERE channelid = ? and serverid = ?'''
        c.execute(query, (ctx.message.channel.id, ctx.message.guild.id,))
        check_exist = c.fetchone()
        if check_exist is not None:
            await ctx.send('```' + check_exist[0] + '```')
        else:
            await ctx.send('No data')


@bot.command(pass_context=True)
async def private(ctx):
    """Pms ticket data to the admin"""
    if ctx.message.author.guild_permissions.administrator:
        await Message.delete(ctx.message)
        query = '''SELECT content FROM tickets WHERE channelid = ? and serverid = ?'''
        c.execute(query, (ctx.message.channel.id, ctx.message.guild.id,))
        check_exist = c.fetchone()
        if check_exist is not None:
            await ctx.message.author.send('```' + check_exist[0] + '```')
        else:
            await ctx.send('No data')


@bot.command(pass_context=True)
async def ids(ctx):
    """Returns a CSV file of all users on the server. May take some time."""
    if ctx.message.author.guild_permissions.administrator:
        await bot.request_offline_members(ctx.message.guild)
        print("This may take a while.")
        before = time.time()
        nicknames = [m.id for m in ctx.message.guild.members]
        with open('ids.csv', mode='w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f, dialect='excel')
            for v in nicknames:
                writer.writerow([await bot.get_user_info(v)])
        after = time.time()
        await bot.send_file(ctx.message.author, 'ids.csv', filename='ids.csv',
                            content="Also saved locally in ids.csv. Compiled in {:.4}ms.".format(
                                (after - before) * 1000))


@bot.command(pass_context=True)
async def sendids(ctx):
    """Sends a pm to all users on previously generated ids.txt"""
    if ctx.message.author.guild_permissions.administrator:
        if os.path.isfile('ids.txt'):
            f = open('ids.txt')
            line = f.readline()
            while line:
                recip = await bot.get_user_info(line)
                try:
                    time.sleep(.1)
                    await recip.send(ctx.message.content[len(command_prefix) + 8:])
                except:
                    print('Can not send to ' + recip)
                line = f.readline()
            f.close()
        else:
            ctx.message.author.send("You haven't generated an ids.txt file. Run ```" + command_prefix
                                    + 'textids```')
            print("You haven't generated an ids.txt file. Run '''" + command_prefix + 'textids```')


@bot.command(pass_context=True)
async def textids(ctx):
    """Generate a local text file of ids"""
    if ctx.message.author.guild_permissions.administrator:
        await bot.request_offline_members(ctx.message.guild)
        id_numbers = [m.id for m in ctx.message.guild.members]
        all_ids = ''
        for v in id_numbers:
            if all_ids == '':
                all_ids = v
            else:
                all_ids = all_ids + '\n' + v
        f = open('ids.txt', "w")
        f.write(all_ids)
        f.close()


@bot.command(pass_context=True)
async def done(ctx):
    """Work in progress system to automatically accept btc"""
    if ctx.message.author.guild_permissions.administrator:
        server = ctx.guild
        c.execute('''SELECT address FROM Addresses WHERE (serverid=? and
                 ticket IS NULL)''', (server.id,))
        addr = c.fetchone()

        if addr is not None:
            dollars_due = float(re.sub("[^0-9.]+", '', ctx.message.content[len(command_prefix) + 5:]))
            amount_due = dollars_to_btc(dollars_due)
            msg = await ctx.send('Please send ' + str(amount_due) + ' bitcoin to ' + addr[0] + ' within 60 minutes')
            query = '''UPDATE tickets SET address=?,  requiredbtc=?, dollaramnt=?, senttime=?,
             messageid=?, paymentattempt = 1 WHERE channelid=? and serverid=?'''
            sent_time = time.time()
            msg_id = msg.id
            c.execute(query, (
                addr[0], amount_due, dollars_due, sent_time, msg_id, ctx.message.channel.id, ctx.message.guild.id,))
            query = '''SELECT ticket FROM tickets WHERE channelid = ? and serverid = ?'''
            c.execute(query, (ctx.message.channel.id, ctx.message.guild.id,))
            ticket_number = c.fetchone()[0]
            c.execute('''UPDATE Addresses SET ticket=? WHERE address=?''', (ticket_number, addr[0]))
            conn.commit()
        else:
            await ctx.send('Please generate some (more?) addresses.')


@bot.command(pass_context=True)
async def seed(ctx):
    """Add 50 receiving addresses to the database. RUN ONCE"""
    await Message.delete(ctx.message)
    if ctx.message.author is ctx.message.guild.owner:
        c.execute('''SELECT address FROM Addresses WHERE serverid=?''', (ctx.message.guild.id,))
        already_ran = c.fetchone()
        if already_ran is None:
            server = ctx.message.guild
            server_id = server.id
            k = keystore.from_seed(ctx.message.content[len(command_prefix) + 5:], '', False)
            for x in range(0, 49):
                addr = bitcoin.pubkey_to_address('p2pkh', k.derive_pubkey(False, x))
                addr_balance = get_balance(addr)
                c.execute('''INSERT INTO Addresses (serverid, address, balance)
                                                      VALUES(?,?,?)''', (server_id, addr, addr_balance,))
            conn.commit()
            await ctx.message.author.send("50 btc addresses have been generated and stored.")
        else:
            await ctx.send("Addresses already generated.")


async def delete_channel(server_id, channel_id):
    channel = await get_channel(server_id, channel_id)
    await channel.delete()


async def update_payment(message_id, channel_id, new_btc, address, author_id, server_id, payment_attempt):
    conn3 = sqlite3.connect('database/data.db')
    c3 = conn3.cursor()
    update = "<@!" + str(author_id) + "> Please send the updated amount of " + str(new_btc) + " btc to " + str(
        address) + "\nThis is attempt number " + str(payment_attempt + 1)
    message = await get_message(server_id, channel_id, message_id)
    channel = await get_channel(server_id, channel_id)
    await Message.delete(message)
    new_message = await channel.send(update)
    query = '''UPDATE tickets SET requiredbtc=?, senttime=?, messageid = ?, paymentattempt = paymentattempt + 1
                            WHERE channelid=? and serverid=?'''
    c3.execute(query, (new_btc, time.time(), new_message.id, channel_id, server_id,))
    conn3.commit()


async def payment_time_left(server_id, channel_id, message_id, amount_due, address, sent_time, payment_attempt,
                            user_id):
    time_left = 60 - round((time.time() - float(sent_time)) / 60)
    try:
        if payment_attempt <= 1:
            update = 'Please send ' + str(amount_due) + ' bitcoin to ' + address + ' within ' + str(
                time_left) + ' minutes'
        else:
            update = "<@!" + str(user_id) + "> Please send the updated amount of " + str(amount_due) + " btc to " + str(
                address) + "\nThis is attempt number **" + str(payment_attempt) + "**"
        message = await get_message(server_id, channel_id, message_id)
        await message.edit(content=update)
    except Exception:
        print('Payment_Time_Left Error:')
        print(Exception)


async def get_channel(server_id, channel_id):
    channel = None
    try:
        guild = bot.get_guild(server_id)
        for x in guild.channels:
            if str(x.id) == str(channel_id):
                channel = x
                break
    except Exception:
        print('Get_Channel Error:')
        print(Exception)
    return channel


async def get_message(server_id, channel_id, message_id):
    message = None
    try:
        channel = await get_channel(server_id, channel_id)
        message = await channel.fetch_message(message_id)
    except Exception:
        print('Get_Message Error:')
        print(Exception)
    return message


def combine_server_string(server):
    return '[' + clean_string(server.name) + ":" + str(server.id) + ']'


def get_balance(address):
    response = requests.get("https://blockchain.info/address/" + address + '?format=json')
    if response.status_code != 200:
        return None
    balance = round(float(response.json()['final_balance'] / 100000000), 5)
    return balance


def dollars_to_btc(dollars_due):
    bitcoin_api_url = 'https://www.bitstamp.net/api/ticker/'
    response = requests.get(bitcoin_api_url)
    response_json = response.json()
    btc_price = float(response_json['bid'])
    return round(dollars_due / btc_price, 4)


def clean_string(string):
    cleaned_string = re.sub("[^0-9a-zA-Z ']+", '', string)
    return cleaned_string


def check_payments():
    conn2 = sqlite3.connect('database/data.db')
    c2 = conn2.cursor()
    for server in bot.guilds:
        query = '''SELECT channelid,messageid,address,requiredbtc,dollaramnt,senttime,userid,paymentattempt FROM tickets WHERE requiredbtc IS NOT NULL'''
        prerequired = c2.execute(query)
        required = prerequired.fetchall()
        if required is not None:
            for k in required:
                print(k)
                channel_id = k[0]
                message_id = k[1]
                addr = k[2]
                required_btc = k[3]
                dollars_due = k[4]
                sent_time = k[5]
                user_id = k[6]
                payment_attempt = k[7]
                c2.execute('''SELECT balance FROM Addresses WHERE address=?''', (addr,))
                start_balance = c2.fetchone()[0]
                if start_balance is not None:
                    server_id = server.id
                    if (float(start_balance) + float(get_balance(addr))) > float(required_btc):
                        print("Ticket paid")
                        query = '''DELETE FROM tickets WHERE address=? and channelid=? and serverid=?'''
                        c2.execute(query, (addr, channel_id, server_id))
                        conn2.commit()
                        asyncio.run_coroutine_threadsafe(delete_channel(server_id, channel_id), loop)
                    elif float(time.time()) > float(sent_time) + 3600:
                        print("Ticket out of time")
                        new_btc = dollars_to_btc(dollars_due)
                        asyncio.run_coroutine_threadsafe(update_payment(message_id, channel_id, new_btc, addr, user_id,
                                                                        server_id, payment_attempt), loop)
                    else:
                        asyncio.run_coroutine_threadsafe(payment_time_left(server_id, channel_id, message_id,
                                                                           required_btc, addr, sent_time,
                                                                           payment_attempt, user_id), loop)
    threading.Timer(10, check_payments).start()


if __name__ == '__main__':
    generate_database()
    generate_settings_file()
    get_constants()
    while True:
        try:
            bot.run(token)
        except Exception as e:
            print(e)
            print("Error starting up bot")
            time.sleep(3)
