# check_veritas_alerts_parser.py
Checks a generated XML from Veritas NetBackup Appliance for statuses and such...

# Requirements:
* Requires modifying the locked down NetBackup Appliance to generate and copy out an XML file. Does not require Icinga2 on the appliance or otherwise modifying it.
-- Easily done with a pub key to a special user account on the icinga server, thus you dont comprimise anything inbound to the Appliance.
* Set up a cronjob which can copy the Alerts XML to a place for parsing, like the icinga2 server.

## Configuring the NetBackup appliance
First, log in to the appliance via SSH
1. Log in as admin via ssh
2. Support
3. Support> Maintenance
4. ```su -```

### SSH keys setup
1. Generate a SSH key pair (```ssh-keygen```)
2. Copy the contents of the .pub key to your designated user account on the host that will run the script. (```.ssh/authorized_keys```)
3. Try to ssh using the following format: ssh <remote SSH login>@<remote host> from the appliance to verify it can connect to it over SSH.

### Crontab - assuming run every 10 minutes
1. ```crontab -e```
2. ```3-59/10 * * * * su - -c 'perl /opt/autosupport/legacy/scripts/hwmon/monitoring.pl --dontdisplay --cron'```
3. ```4-59/10 * * * * scp /tmp/alerts.xml <remote SSH login>@<remote host>:<filename>```
 - I recommend using the filename <fqdn-alerts.xml> for a clear indiciation of its source.


# Checks available
## Appliance
* epoch
-- Alerts timestamp, is the file we are parsing new enough?
* disks
* fans
* fibrechannels
* msdps
* partitions
* powers
* raidgroups
* temperatures
## Enclosure
* disks
* fans
* powers
* temperatures

## Icinga2 CheckCommand definition
```
object CheckCommand "veritas_alerts_parser" {
    import "plugin-check-command"
    command = [ PluginDir + "/check_veritas_alerts_parser.py" ]
    timeout = 10s
    arguments += {
        "--appliance-check" = {
            description = "Check to execute"
            value = "$veritas_appliance_check$"
        }
        "--critical" = "$veritas_critical$"
        "--enclosure-check" = {
            description = "Enclosure check to execute"
            value = "$veritas_enclosure_check$"
        }
        "--warning" = "$veritas_warning$"
        "--xmlfile" = {
            description = "Full path to the XML file containing the Veritas XML file"
            required = true
            value = "$veritas_filepath$"
        }
    }
}
```
