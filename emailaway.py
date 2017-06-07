from datetime import datetime
import os
from smtplib import SMTP

import znc


class mailtimer(znc.Timer):
    nick = None

    def RunJob(self):
        module = self.GetModule()
        filepath = os.path.join(module.SavePath, self.nick)
        text = ''

        with open(filepath, 'r') as f:
            text = f.read()

        del module.timers[self.nick]
        os.remove(filepath)

        module.SendEmail('New Messages from {0}'.format(self.nick), text)


class emailaway(znc.Module):
    module_types = [znc.CModInfo.NetworkModule]
    description = 'ZNC module to email messages received while away'

    commands = []

    timers = {}

    def AddCommand(self, name, func, args, desc):
        if len([x for x in self.commands if x[0] == name]) == 0:
            self.commands.append((name, func, args, desc))
        else:
            raise Exception('Non-uniq command given! Cannot add to list')

    def CommandHelp(self, args):

        cmdlist = [('{0} {1}'.format(x[0], x[2]).strip(), x[3])
                   for x in self.commands if len(args) == 0 or
                   x[0].lower() == args.lower()]

        if len(cmdlist) == 0:
            self.PutModule('No Matches for \'{0}\''.format(args))
            return znc.CONTINUE

        cmd_header = 'Command'
        desc_header = 'Description'

        max_cmd_len = len(cmd_header)
        max_desc_len = len(desc_header)

        for cmd in cmdlist:
            if len(cmd[0]) > max_cmd_len:
                max_cmd_len = len(cmd[0])
            if len(cmd[1]) > max_desc_len:
                max_desc_len = len(cmd[1])

        max_cmd_len += 2
        max_desc_len += 2

        header = '+{0}+{1}+'.format('=' * max_cmd_len, '=' * max_desc_len)
        divider = '+{0}+{1}+'.format('-' * max_cmd_len, '-' * max_desc_len)

        self.PutModule(header)
        self.PutModule('| {0}{1}| {2}{3}|'.format(
            cmd_header, ' ' * (max_cmd_len - len(cmd_header) - 1),
            desc_header, ' ' * (max_desc_len - len(desc_header) - 1)))
        self.PutModule(header)

        first = True
        for cmd in cmdlist:
            if first:
                first = False
            else:
                self.PutModule(divider)
            self.PutModule('| {0}{1}| {2}{3}|'.format(
                cmd[0], ' ' * (max_cmd_len - len(cmd[0]) - 1),
                cmd[1], ' ' * (max_desc_len - len(cmd[1]) - 1)))

        self.PutModule(header)

        return znc.CONTINUE

    def CommandListTimers(self, args):
        if len(self.timers) == 0:
            self.PutModule('No pending timers')
        elif args is None or len(args) == 0:
            for t in self.timers.keys():
                self.PutModule('{0}: {1}'
                               .format(t, self.timers[t]['plannedSend']))
        else:
            if args in self.timers.keys():
                for k in self.timers[args].keys():
                    if k is not 'timer':
                        self.PutModule('{0}: {1}'
                                       .format(k, self.timers[args][k]))

        return znc.CONTINUE

    def CommandMailHost(self, args):
        return self.GetSetStr('MailHost', args)

    def CommandMailPort(self, args):
        return self.GetSetInt('MailPort', args)

    def CommandMaxMessages(self, args):
        return self.GetSetInt('MaxMessages', args)

    def CommandRecipientEmail(self, args):
        return self.GetSetStr('RecipientEmail', args)

    def CommandSenderEmail(self, args):
        return self.GetSetStr('SenderEmail', args)

    def CommandSendDelay(self, args):
        return self.GetSetInt('SendDelay', args)

    def CommandSendTestEmail(self, args):
        msg = 'This is a test message from ZNC.'
        if len(args) > 0:
            msg += '\n\n{0}'.format(args)
        self.SendEmail('ZNC Test Email', msg)

    def GetSetInt(self, key, value=None):
        if value:
            try:
                int(value)
            except ValueError:
                self.PutModule('{0} must be an integer'.format(key))
            else:
                if not self.SetNV(key, value):
                    self.PutModule('Error setting "{0}" to "{1}"'
                                   .format(key, value))
        value = self.GetNV(key)
        self.PutModule('{0}: {1}'.format(key, value))
        return znc.CONTINUE

    def GetSetStr(self, key, value=None):
        if value:
            if not self.SetNV(key, value):
                self.PutModule('Error setting "{0}" to "{1}"'
                               .format(key, value))
        value = self.GetNV(key)
        self.PutModule('{0}: {1}'.format(key, value))
        return znc.CONTINUE

    def IsAway(self):
        return self.GetNetwork().IsIRCAway()

    def OnLoad(self, args, message):
        self.SavePath = os.path.join(self.GetSavePath(), 'logs')
        if not os.path.isdir(self.SavePath):
            os.mkdir(self.SavePath)

        self.AddCommand('Help', self.CommandHelp, '[command]',
                        'Display module help (this message)')
        self.AddCommand('SendTestEmail', self.CommandSendTestEmail,
                        '[message]', 'Send a test email')
        self.AddCommand('ListTimers', self.CommandListTimers, '',
                        'List current pending emails')
        self.AddCommand('MailHost', self.CommandMailHost,
                        '[hostName_or_IP]',
                        'Get/set email SMTP host to send to')
        self.AddCommand('MailPort', self.CommandMailPort,
                        '[port]',
                        'Get/set server port to use when sending')
        self.AddCommand('MaxMessages', self.CommandMaxMessages,
                        '[count]',
                        'Get/set max number of messages before sending')
        self.AddCommand('RecipientEmail', self.CommandRecipientEmail,
                        '[emailAddress]',
                        'Get/set recipient address for away message delivery')
        self.AddCommand('SenderEmail', self.CommandSenderEmail,
                        '[emailAddress]',
                        'Get/set address to send away messages from')
        self.AddCommand('SendDelay', self.CommandSendDelay,
                        '[seconds]',
                        'Get/set number of seconds to wait before sending')
        self.commands.sort(key=lambda x: x[0])

        if not self.ExistsNV('MailHost'):
            self.SetNV('MailHost', 'localhost')
        if not self.ExistsNV('MailPort'):
            self.SetNV('MailPort', '25')
        if not self.ExistsNV('MaxMessages'):
            self.SetNV('MaxMessages', '30')
        if not self.ExistsNV('RecipientEmail'):
            self.SetNV('RecipientEmail', 'user@localhost.localdomain')
        if not self.ExistsNV('SenderEmail'):
            self.SetNV('SenderEmail', 'znc-emailaway@localhost.localdomain')
        if not self.ExistsNV('SendDelay'):
            self.SetNV('SendDelay', '30')

        return znc.CONTINUE

    def OnModCommand(self, cmd):
        for command in self.commands:
            if cmd.lower().startswith(command[0].lower()):
                try:
                    return command[1](cmd[len(command[0]):].strip())
                except Exception as e:
                    self.PutModule('Error calling function! {0}'.format(e))

        self.PutModule('Could not interpret command')
        return znc.CONTINUE

    def OnPrivAction(self, nick, msg):
        return self.ProcessPM(nick, msg, isAction=True)

    def OnPrivMsg(self, nick, msg):
        return self.ProcessPM(nick, msg)

    def ProcessPM(self, nick, msg, isAction=False):
        nick = str(nick)
        msg = str(msg)
        if self.IsAway():
            msgDate = datetime.now()

            if isAction:
                logline = '{0} * {1} {2}\n'.format(msgDate, nick, msg)
            else:
                logline = '{0} <{1}> {2}\n'.format(msgDate, nick, msg)

            try:
                with open(os.path.join(self.SavePath, str(nick)), 'a') as f:
                    f.write(logline)
            except Exception as e:
                self.PutModule('ERROR: {0}'.format(e))
                raise e

            delay = int(self.GetNV('SendDelay'))
            maxMessages = int(self.GetNV('MaxMessages'))

            if nick in self.timers.keys():
                self.timers[nick]['messageCount'] += 1
                self.timers[nick]['lastMessage'] = msgDate
                if self.timers[nick]['messageCount'] >= maxMessages:
                    self.timers[nick]['timer'].Reset()  # Avoid duplicate runs
                    self.timers[nick]['timer'].RunJob()
                else:
                    self.timers[nick]['timer'].Reset()
                    self.timers[nick]['plannedSend'] = self.\
                        timers[nick]['timer'].GetNextRun()
            else:
                timer = self.CreateTimer(mailtimer, interval=delay, cycles=1,
                                         description='Email delay')
                timer.nick = '{0}'.format(nick)

                self.timers[nick] = {'lastMessage': msgDate,
                                     'messageCount': 1,
                                     'plannedSend': timer.GetNextRun(),
                                     'startDate': msgDate,
                                     'timer': timer}

    def SendEmail(self, subject, msg):
        from_address = self.GetNV('SenderEmail')
        to_address = self.GetNV('RecipientEmail')
        msg = '\n'.join(['From: ZNC EmailAway <{0}>'.format(from_address),
                         'To: <{0}>'.format(to_address),
                         'MIME-Version: 1.0',
                         'Content-type: text/plain',
                         'Subject: {0}'.format(subject),
                         '',
                         msg])

        try:
            with SMTP(self.GetNV('MailHost'),
                      port=int(self.GetNV('MailPort'))) as smtp:
                smtp.sendmail(self.GetNV('SenderEmail'),
                              self.GetNV('RecipientEmail'), msg)
        except Exception as e:
            self.PutModule('Error sending mail: {0}'.format(e))
