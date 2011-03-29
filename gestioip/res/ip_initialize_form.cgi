#!/usr/bin/perl -T -w

# Copyright (C) 2011 Marc Uebel

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


use strict;
use lib '../modules';
use GestioIP;

my $daten=<STDIN>;
my $gip = GestioIP -> new();
my %daten=$gip->preparer($daten);

my $base_uri = $gip->get_base_uri();
my $server_proto=$gip->get_server_proto();

my $lang = $daten{'lang'} || "";
my ($lang_vars,$vars_file)=$gip->get_lang("","$lang");

my $client_id = $daten{'client_id'} || $gip->get_first_client_id();

$gip->CheckInput("$client_id",\%daten,"$$lang_vars{mal_signo_error_message}","$$lang_vars{initialize_gestioip_message}","$vars_file");

my $hide1_v6=$$lang_vars{snmp_username_message};
my $hide2_v6=$$lang_vars{security_level_message};
my $hide3_v6="<select name=\\\"sec_level\\\" id=\\\"sec_level\\\"> <option value=\\\"noAuthNoPriv\\\">noAuthNoPriv</option> <option value=\\\"authNoPriv\\\" selected>authNoPriv</option> <option value=\\\"authPriv\\\">authPriv</option>";
my $hide4_v6=$$lang_vars{auth_proto_message};
my $hide5_v6=$$lang_vars{auth_pass_message};
my $hide6_v6="<select name=\\\"auth_proto\\\" id=\\\"auth_proto\\\"><option value=\\\"\\\" selected>---</option> <option value=\\\"MD5\\\">MD5</option> <option value=\\\"SHA\\\">SHA</option></select>";
my $hide7_v6="<input type=\\\"password\\\" size=\\\"15\\\" name=\\\"auth_pass\\\" id=\\\"auth_pass\\\" maxlength=\\\"100\\\">";
my $hide8_v6=$$lang_vars{priv_proto_message};
my $hide9_v6=$$lang_vars{priv_pass_message};
my $hide10_v6="<select name=\\\"priv_proto\\\" id=\\\"priv_proto\\\"> <option value=\\\"\\\" selected>---</option> <option value=\\\"DES\\\" >DES</option> <option value=\\\"3DES\\\">3DES</option> <option value=\\\"AES\\\">AES</option></select>";
my $hide11_v6="<input type=\\\"password\\\" size=\\\"15\\\" name=\\\"priv_pass\\\" id=\\\"priv_pass\\\" maxlength=\\\"100\\\">";


print <<EOF;

<script type="text/javascript">
<!--
function changeText1(version){
  if(version == 1 | version == 2 ) {
    document.getElementById('Hide1').innerHTML = "$$lang_vars{snmp_community_message}";
    document.getElementById('Hide2').innerHTML = "";
    document.getElementById('Hide3').innerHTML = "";
    document.getElementById('Hide4').innerHTML = "";
    document.getElementById('Hide5').innerHTML = "";
    document.getElementById('Hide6').innerHTML = "";
    document.getElementById('Hide7').innerHTML = "";
    document.getElementById('Hide8').innerHTML = "";
    document.getElementById('Hide9').innerHTML = "";
    document.getElementById('Hide10').innerHTML = "";
    document.getElementById('Hide11').innerHTML = "";
    document.forms.snmp_version.community_string.type="password";
    document.forms.snmp_version.community_string.value="public";
  }else{
    document.getElementById('Hide1').innerHTML = "$hide1_v6";
    document.getElementById('Hide2').innerHTML = "$hide2_v6";
    document.getElementById('Hide3').innerHTML = "$hide3_v6";
    document.getElementById('Hide4').innerHTML = "$hide4_v6";
    document.getElementById('Hide5').innerHTML = "$hide5_v6";
    document.getElementById('Hide6').innerHTML = "$hide6_v6";
    document.getElementById('Hide7').innerHTML = "$hide7_v6";
    document.getElementById('Hide8').innerHTML = "$hide8_v6";
    document.getElementById('Hide9').innerHTML = "$hide9_v6";
    document.getElementById('Hide10').innerHTML = "$hide10_v6";
    document.getElementById('Hide11').innerHTML = "$hide11_v6";
    document.forms.snmp_version.community_string.type="text";
    document.forms.snmp_version.community_string.value="";
  }
}
-->
</script>


<script type="text/javascript">
<!--
function checkRefresh() {
  document.forms.snmp_version.snmp_version.selectedIndex="0";
}
-->
</script>

EOF

my @values_max_procs = ("32","64","128","254");

print "<p>\n";
print "<form name=\"snmp_version\" method=\"POST\" action=\"$server_proto://$base_uri/res/ip_initialize.cgi\">\n";
print "<table border=\"0\" cellpadding=\"7\">\n";
print "<tr><td align=\"right\"><p>$$lang_vars{ini_devices_message}</td><td><textarea name=\"ini_devices\" cols=\"30\" rows=\"5\" wrap=\"physical\" maxlength=\"500\"></textarea></td><td valign=\"bottom\"> (<i>$$lang_vars{coma_separated_list_of_message}</i>)</td></tr>\n";
#print "<tr><td align=\"right\"><p><b>$$lang_vars{community_string_message}</b></td><td><input type=\"password\" size=\"10\" name=\"community_string\" value=\"public\" maxlength=\"55\"> $$lang_vars{snmp_default_public_message}</td></tr>\n";
#print "<tr><td align=\"right\">$$lang_vars{snmp_v1_message}</td><td><input type=\"radio\" name=\"snmp_version\" value=\"1\" checked></td></tr>\n";
#print "<tr><td align=\"right\">$$lang_vars{snmp_v2c_message}</td><td><input type=\"radio\" name=\"snmp_version\" value=\"2\"></td></tr>\n";
#print "<tr><td align=\"right\">$$lang_vars{snmp_v3_message}</td><td><input type=\"radio\" name=\"snmp_version\" value=\"3\"></td></tr>\n";
#print "</td></tr>\n";



print <<EOF;
        <tr><td align="right">$$lang_vars{snmp_version_message}</td>
        <td colspan="3"><select name="snmp_version" id="snmp_version" onchange="changeText1(this.value);">


        <option value="1" selected>v1</option>
        <option value="2">v2c</option>
        <option value="3">v3</option>
        </select>
        </td></tr>


	<tr><td align="right">
        <span id="Hide1">$$lang_vars{snmp_community_message}</span>
        </td><td colspan="3"><input type="password" size="10" name="community_string" value="public" maxlength="55">$$lang_vars{snmp_default_public_message}</td></tr>


        <tr><td align="right">
        <span id="Hide2"></span>
        </td><td colspan=\"3\">
        <span id="Hide3"></span>
        </select>
	</span>

        </td></tr>

        <tr><td align="right"></td><td><span id="Hide4"></span></td><td><span id="Hide5"></span></td><td></td></tr>

        <tr><td align="right"></td><td>
	<span id="Hide6"></span>
        </select>

        </td><td><span id="Hide7"></span></td><td></tr>

        <tr><td align="right"></td><td><span id="Hide8"></span></td><td><span id="Hide9"></span></td><td></td></tr>

        <tr><td align="right"></td><td>
	<span id="Hide10"></span>
        </td><td><span id="Hide11"></span></td><td></tr>

EOF





print "<tr><td align=\"right\"><br>$$lang_vars{max_sinc_procs_manage_message}</td><td><br><select name=\"max_procs\" size=\"1\">\n";
foreach (@values_max_procs) {
        if ( $_ eq "128" ) {
                print "<option selected>$_</option>";
                next;
        }
        print "<option>$_</option>";
}
print "</select>\n";
print "</td></tr>\n";

print "<tr><td align=\"right\"><br>$$lang_vars{include_spread_nets_message}</td><td><br><input type=\"checkbox\" name=\"include_spreadsheet_networks\" value=\"yes\" checked></td></tr>\n";
print "<tr><td align=\"right\"><br>$$lang_vars{add_comment_snmp_query_message}</td><td><br><input type=\"checkbox\" name=\"add_comment\" value=\"yes\">(<i>$$lang_vars{add_comment_example_message}</i>)</td></tr>\n";
print "<tr><td><br><input type=\"hidden\" name=\"client_id\" value=\"$client_id\"><input type=\"submit\" value=\"$$lang_vars{discover_message}\" name=\"B1\" class=\"input_link_w\"></td></tr>\n";
print "</form>\n";
print "</table>\n";

$gip->print_end("$client_id");
