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
use Net::IP;
use Net::IP qw(:PROC);
use lib '../modules';
use GestioIP;


my $daten=<STDIN>;
my $gip = GestioIP -> new();
my %daten=$gip->preparer($daten);

my $base_uri = $gip->get_base_uri();
my $server_proto=$gip->get_server_proto();

my $lang = $daten{'lang'} || "";
my ($lang_vars,$vars_file,$entries_per_page_hosts);
($lang_vars,$vars_file)=$gip->get_lang("","$lang");
if ( $daten{'entries_per_page_hosts'} && $daten{'entries_per_page_hosts'} =~ /^\d{1,3}$/ ) {
        $entries_per_page_hosts=$daten{'entries_per_page_hosts'};
} else {
        $entries_per_page_hosts = "254";
}

my $client_id = $daten{'client_id'} || $gip->get_first_client_id();
my $host_order_by = $daten{'host_order_by'} || "IP_auf";
my $ip_version = $daten{'ip_version'} || "";


my $ip_int=$daten{'ip'};
my $red_num=$daten{'red_num'};
my $loc=$daten{'loc'};
$loc = "" if $loc eq "---";


my $ip_ad=$gip->int_to_ip("$client_id","$ip_int","$ip_version");

$gip->CheckInput("$client_id",\%daten,"$$lang_vars{mal_signo_error_message}","$$lang_vars{cambiar_host_message} $ip_ad","$vars_file");

my $utype = $daten{'update_type'};
$gip->print_error("$client_id","$$lang_vars{formato_malo_message}") if $daten{'anz_values_hosts'} && $daten{'anz_values_hosts'} !~ /^\d{2,4}||no_value$/;
$gip->print_error("$client_id","$$lang_vars{formato_malo_message}") if $daten{'knownhosts'} && $daten{'knownhosts'} !~ /^all|hosts|libre$/;
$gip->print_error("$client_id","$$lang_vars{formato_malo_message}") if $daten{'start_entry_hosts'} && $daten{'start_entry_hosts'} !~ /^\d{1,20}$/;
#$gip->print_error("$client_id","$$lang_vars{formato_malo_message}") if ! $daten{'host_id'};
my $anz_values_hosts = $daten{'anz_values_hosts'} || "no_value";

my $start_entry_hosts=$daten{'start_entry_hosts'} || '0';
my $knownhosts=$daten{'knownhosts'} || 'all';
my $host_id=$daten{'host_id'} || "";

print "<p>\n";

$daten{'ip'} || $gip->print_error("$client_id","$$lang_vars{una_ip_message}<br>");

if ( $ip_version eq "v4" ) {
	$gip->CheckInIP("$client_id","$ip_ad","$$lang_vars{formato_ip_malo_message} - $$lang_vars{comprueba_ip_message}: <b><i>$ip_ad</i></b><br>");
} else {
	my $valid_v6=$gip->check_valid_ipv6("$ip_ad") || "0";
	$gip->print_error("$client_id","$$lang_vars{formato_ip_malo_message}") if $valid_v6 ne "1";
}

my @values_redes = $gip->get_red("$client_id","$red_num");

my $red = "$values_redes[0]->[0]" || "";
my $BM = "$values_redes[0]->[1]" || "";

my @values_locations=$gip->get_loc("$client_id");
my @values_categorias=$gip->get_cat("$client_id");
my @values_utype=$gip->get_utype();

my @host=$gip->get_host("$client_id","$ip_int","$ip_int");

my $hostname = $host[0]->[1] || "";
$hostname = "" if $hostname eq "NULL";
my $host_descr = $host[0]->[2] || "NULL";
my $loc_val = $host[0]->[3] || "$loc";
my $cat_val = $host[0]->[4] || "NULL";
my $int_ad_val = $host[0]->[5] || "n";
my $update_type = $host[0]->[7] || "";
my $comentario = $host[0]->[6] || "";

$host_descr = "" if (  $host_descr eq "NULL" );
$comentario = "" if (  $comentario eq "NULL" ); 
$loc_val = "" if (  $loc_val eq "NULL" ); 
$cat_val = "" if (  $cat_val eq "NULL" );
$update_type = "" if (  $update_type eq "NULL" ); 


print <<EOF;
<script language="JavaScript" type="text/javascript" charset="utf-8">
<!--
function checkhost(IP,HOSTNAME,CLIENT_ID,IP_VERSION)
{
var opciones="toolbar=no,right=100,top=100,width=500,height=300", i=0;
var URL="$server_proto://$base_uri/ip_checkhost.cgi?ip=" + IP + "&hostname=" + HOSTNAME + "&client_id=" + CLIENT_ID  + "&ip_version=" + IP_VERSION;
host_info=window.open(URL,"",opciones);
}
-->
</script>
EOF


print "<form name=\"ip_mod_form\" method=\"POST\" action=\"$server_proto://$base_uri/res/ip_modip.cgi\">\n";
print "<table border=\"0\" cellpadding=\"1\">\n";
print "<font size=\"1\"><tr><td><b>IP</b></td><td><b>  $$lang_vars{hostname_message}</font></b></td><td><b>  $$lang_vars{description_message}</b></td><td><b>  $$lang_vars{loc_message}</b></td><td><b> $$lang_vars{cat_message}</b></td><td><b>AI</b></td><td><b>$$lang_vars{comentario_message}</b></td><td><b>UT</b></td></tr>\n";
print "<tr valign=\"top\"><td class=\"hostcheck\" onClick=\"checkhost(\'$ip_ad\',\'\',\'$client_id\',\'$ip_version\')\" style=\"cursor:pointer;\" title=\"ping\"><font size=\"2\">$ip_ad<input type=\"hidden\" name=\"ip\" value=\"$ip_ad\"></font></td>\n";
print "<td><i><font size=\"2\"><input type=\"text\" size=\"15\" name=\"hostname\" value=\"$hostname\" maxlength=\"45\"></font></i></td>\n";
print "<td><i><font size=\"2\"><input type=\"text\" size=\"15\" name=\"host_descr\" value=\"$host_descr\" maxlength=\"100\"></font></i></td>\n";
print "<td><font size=\"2\"><select name=\"loc\" size=\"1\" value=\"$loc_val\">";
print "<option>$loc_val</option>";
my $j=0;
foreach (@values_locations) {
	$values_locations[$j]->[0] = "" if ($values_locations[$j]->[0] eq "NULL" && $loc_val ne "NULL" );
	print "<option>$values_locations[$j]->[0]</option>" if ( $values_locations[$j]->[0] ne "$loc_val" );
	$j++;
}
print "</td><td><select name=\"cat\" size=\"1\">";
print "<option>$cat_val</option>";
$j=0;
foreach (@values_categorias) {
	$values_categorias[$j]->[0] = "" if ($values_categorias[$j]->[0] eq "NULL" && $cat_val ne "NULL" );
        print "<option>$values_categorias[$j]->[0]</option>" if ($values_categorias[$j]->[0] ne "$cat_val" );
        $j++;
}
my $int_admin_checked;
if ( $int_ad_val eq "y" ) {
	$int_admin_checked="checked";
} else {
	$int_admin_checked="";
}
print "</select></font></td><input name=\"red\" type=\"hidden\" value=\"$red\"><input name=\"BM\" type=\"hidden\" value=\"$BM\"><input name=\"red_num\" type=\"hidden\" value=\"$red_num\"><td><input type=\"checkbox\" name=\"int_admin\" value=\"y\" $int_admin_checked></td>\n";


print "<td><textarea name=\"comentario\" cols=\"30\" rows=\"5\" wrap=\"physical\" maxlength=\"500\">$comentario</textarea></td>";
print "<td><select name=\"update_type\" size=\"1\">";
print "<option>$update_type</option>";
$j=0;
foreach (@values_utype) {
	$values_utype[$j]->[0] = "" if ( $values_utype[$j]->[0] =~ /NULL/ && $update_type ne "NULL" );
        print "<option>$values_utype[$j]->[0]</option>" if ( $values_utype[$j]->[0] ne "$update_type" );
        $j++;
}
print "</select>\n";
print "</td>";

#print "<td><input name=\"entries_per_page_hosts\" type=\"hidden\" value=\"$entries_per_page_hosts\"><input name=\"start_entry_hosts\" type=\"hidden\" value=\"$start_entry_hosts\"><input name=\"host_order_by\" type=\"hidden\" value=\"$host_order_by\"><input name=\"knownhosts\" type=\"hidden\" value=\"$knownhosts\"><input name=\"anz_values_hosts\" type=\"hidden\" value=\"$anz_values_hosts\"><input name=\"client_id\" type=\"hidden\" value=\"$client_id\"><input type=\"submit\" value=\"$$lang_vars{cambiar_message}\" name=\"B1\"></td></tr>\n";
#print "</form>\n";
#print "</table>\n";
print "<td><input name=\"entries_per_page_hosts\" type=\"hidden\" value=\"$entries_per_page_hosts\"><input name=\"start_entry_hosts\" type=\"hidden\" value=\"$start_entry_hosts\"><input name=\"knownhosts\" type=\"hidden\" value=\"$knownhosts\"><input name=\"anz_values_hosts\" type=\"hidden\" value=\"$anz_values_hosts\"></td></tr>\n";


print "<br><p>\n";
print "<table border=\"0\" cellpadding=\"1\">\n";

my %cc_value = ();
my @custom_columns = $gip->get_custom_host_columns("$client_id");
%cc_value=$gip->get_custom_host_columns_from_net_id_hash("$client_id","$host_id") if $host_id;
print "TEST HOLA<br>\n";

if ( $custom_columns[0] ) {
        print "<b>$$lang_vars{custom_host_columns_message}</b><p>\n";
}

my $n=0;
foreach my $cc_ele(@custom_columns) {
	my $cc_name = $custom_columns[$n]->[0];
	my $pc_id = $custom_columns[$n]->[3];
	my $cc_id = $custom_columns[$n]->[1];
	my $cc_entry = $cc_value{$cc_id}[1] || "";

	if ( $cc_name ) {
		print "<tr><td><b>$cc_name</b></td><td><input name=\"custom_${n}_name\" type=\"hidden\" value=\"$cc_name\"><input name=\"custom_${n}_id\" type=\"hidden\" value=\"$cc_id\"><input name=\"custom_${n}_pcid\" type=\"hidden\" value=\"$pc_id\"><input type=\"text\" size=\"20\" name=\"custom_${n}_value\" value=\"$cc_entry\" maxlength=\"500\"></td></tr>\n";
	}
	$n++;
}

print "<tr><td><br><p><input type=\"hidden\" name=\"host_id\" value=\"$host_id\"><input name=\"host_order_by\" type=\"hidden\" value=\"$host_order_by\"><input type=\"hidden\" name=\"client_id\" value=\"$client_id\"><input type=\"hidden\" name=\"ip_version\" value=\"$ip_version\"><input type=\"submit\" value=\"$$lang_vars{cambiar_message}\" name=\"B1\" class=\"input_link_w_net\"></td><td></td></tr>\n";
print "</form>\n";
print "</table>\n";


print "<script type=\"text/javascript\">\n";
print "document.ip_mod_form.hostname.focus();\n";
print "</script>\n";

$gip->print_end("$client_id","$vars_file");
