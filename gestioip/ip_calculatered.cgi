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
use DBI;
use lib './modules';
use GestioIP;
use Net::IP;
use Net::IP qw(:PROC);
use POSIX qw(ceil);

my $daten=<STDIN>;
my $gip = GestioIP -> new();
my %daten=$gip->preparer("$daten") if $daten;

my $base_uri = $gip->get_base_uri();
my ($lang_vars,$vars_file)=$gip->get_lang();
my $server_proto=$gip->get_server_proto();

my $client_id=1;
my $ip_version = $daten{'ip_version'} || 'v4';
my $selected_index=$daten{'selected_index'} || "";

if ( ! $selected_index && $ip_version eq "v4" ) {
	$selected_index=19;
} elsif ( ! $selected_index && $ip_version eq "v6" ) {
	$selected_index="121";
}

print <<EOF;
Content-type: text/html\n
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"
"http://www.w3.org/TR/html4/loose.dtd">
<HTML>
<head><title>Gesti&oacute;IP subnet calculator</title>
<meta http-equiv="content-type" content="text/html; charset=UTF-8">
<link rel="stylesheet" type="text/css" href="./stylesheet.css">
<link rel="shortcut icon" href="/favicon.ico">
</head>

<body onLoad="JavaScript:checkRefresh('$ip_version','$selected_index');">
<div id="TopBoxCalc">
<table border="0" width="100%"><tr height="50px" valign="middle"><td>
  <span class="TopTextGestio">Gesti&oacute;IP</span></td>
  <td><span class="TopText">$$lang_vars{subnet_calculator_message}</span></td><tr>
</td></table>
</div>
<p>
EOF

#my ($red,$BM);
my $red="";
my $BM="";

if ( $ip_version eq "v4" ) {
	if ( $daten{red} && $daten{red} =~ /^\d{8,10}$/ ) {
		$daten{red} =~ s/^\s*//;
		$daten{red} =~ s/\s*$//;
		$red = $gip->int_to_ip("$client_id","$daten{red}","$ip_version");
		$gip->print_error("$client_id","$$lang_vars{formato_malo_message} (1)") if ! $red;
		$BM = $daten{BM};
	} else {
		
		if ( $daten{red} ) {
			$daten{red} =~ s/^\s*//;
			$daten{red} =~ s/\s*$//;
			$gip->CheckInIP("$client_id","$daten{'red'}","$$lang_vars{formato_ip_malo_message} <p><br><p><FORM style=\"display:inline;\"><INPUT TYPE=\"BUTTON\" VALUE=\"back\" ONCLICK=\"history.go(-1)\" class=\"error_back_link\"></FORM><p><br><p><br><p><br><span class=\"close_window\" onClick=\"window.close()\" style=\"cursor:pointer;\"> $$lang_vars{close_message} </span>");
			$gip->print_error("$client_id","$$lang_vars{formato_malo_message} (2) $daten{BM}") if $daten{BM} !~ /^\d{1,2}.+\(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\s-\s[0-9\.]+\shosts\)/ && $daten{BM} !~ /^\d{1,2}$/;
			$red=$daten{red};
			$BM = $daten{BM};
		} elsif ( $ENV{'QUERY_STRING'} ) {
			my $QUERY_STRING = $ENV{'QUERY_STRING'};
			$QUERY_STRING =~ /ip=(.*)&BM=(.*)$/;
			$red=$1; 
			$BM=$2;
		}
	}
	$BM=24 if ! $BM;
} else {
	if ( $daten{red} ) {
		$daten{red} =~ s/^\s*//;
		$daten{red} =~ s/\s*$//;
		$red = $daten{red};
		my $valid_v6 = $gip->check_valid_ipv6("$red") || "0";
		$gip->print_error("$client_id","$$lang_vars{no_valid_ipv6_address_message} <b>$red</b>") if $valid_v6 != "1";
		$gip->print_error("$client_id","$$lang_vars{formato_malo_message} (3)") if $daten{BM} !~ /^\d{1,3}/;
		$BM = $daten{BM};
	}
}

my $red_orig=$red;


print STDERR "TEST: BM: $BM\n";
print <<EOF;

<script type="text/javascript">
<!--
function checkRefresh(version,selected_index) {
 if (version == 'v4') {
  num_values = 28
  document.calculate_form.BM.length = num_values
  var bm_index=document.calculate_form.BM.options[1].value
  document.forms.calculate_form.ip_version[0].checked=true
  document.forms.calculate_form.red.size='15';
  document.forms.calculate_form.BM.options[selected_index].selected=true
 } else {
  document.forms.calculate_form.ip_version[1].checked=true
  num_values = '128'
  document.calculate_form.BM.length = num_values
  document.forms.calculate_form.red.size='38';
  var network_message="$$lang_vars{entradas_redes_message}"
  var values_v6=new Array("1 (9,223,372,036,854,775,808 " + network_message + ")","2 (4,611,686,018,427,387,904 " + network_message + ")","3 (2,305,843,009,213,693,952 " + network_message + ")","4 (1,152,921,504,606,846,976 " + network_message + ")","5 (576,460,752,303,423,488 " + network_message + ")","6 (288,230,376,151,711,744 " + network_message + ")","7 (144,115,188,075,855,872 " + network_message + ")","8 (72,057,594,037,927,936 " + network_message + ")","9 (36,028,797,018,963,968 " + network_message + ")","10 (18,014,398,509,481,984 " + network_message + ")","11 (9,007,199,254,740,992 " + network_message + ")","12 (4,503,599,627,370,496 " + network_message + ")","13 (2,251,799,813,685,248 " + network_message + ")","14 (1,125,899,906,842,624 " + network_message + ")","15 (562,949,953,421,312 " + network_message + ")","16 (281,474,976,710,656 " + network_message + ")","17 (140,737,488,355,328 " + network_message + ")","18 (70,368,744,177,664 " + network_message + ")","19 (35,184,372,088,832 " + network_message + ")","20 (17,592,186,044,416 " + network_message + ")","21 (8,796,093,022,208 " + network_message + ")","22 (4,398,046,511,104 " + network_message + ")","23 (2,199,023,255,552 " + network_message + ")","24 (1,099,511,627,776 " + network_message + ")","25 (549,755,813,888 " + network_message + ")","26 (274,877,906,944 " + network_message + ")","27 (137,438,953,472 " + network_message + ")","28 (68,719,476,736 " + network_message + ")","29 (34,359,738,36 " + network_message + ")","30 (17,179,869,184 " + network_message + ")","31 (8,589,934,592 " + network_message + ")","32 (4,294,967,296 " + network_message + ")","33 (2,147,483,648 " + network_message + ")","34 (1,073,741,824 " + network_message + ")","35 (536,870,912 " + network_message + ")","36 (268,435,456 " + network_message + ")","37 (134,217,728 " + network_message + ")","38 (67,108,864 " + network_message + ")","39 (33,554,432 " + network_message + ")","40 (16,777,216 " + network_message + ")","41 (8,388,608 " + network_message + ")","42 (4,194,304 " + network_message + ")","43 (2,097,152 " + network_message + ")","44 (1,048,576 " + network_message + ")","45 (524,288 " + network_message + ")","46 (262,144 " + network_message + ")","47 (131,072 " + network_message + ")","48 (65,536 " + network_message + ")","49 (32,768 " + network_message + ")","50 (16,384 " + network_message + ")","51 (8,192 " + network_message + ")","52 (4,096 " + network_message + ")","53 (2,048 " + network_message + ")","54 (1,024 " + network_message + ")","55 (512 " + network_message + ")","56 (256 " + network_message + ")","57 (128 " + network_message + ")","58 (64 " + network_message + ")","59 (32 " + network_message + ")","60 (16 " + network_message + ")","61 (8 " + network_message + ")","62 (4 " + network_message + ")","63 (2 " + network_message + ")","64 (18,446,744,073,709,551,616 hosts)","65 (9,223,372,036,854,775,808 hosts)","66 (4,611,686,018,427,387,904 hosts)","67 (2,305,843,009,213,693,952 hosts)","68 (1,152,921,504,606,846,976 hosts)","69 (576,460,752,303,423,488 hosts)","70 (288,230,376,151,711,744 hosts)","71 (144,115,188,075,855,872 hosts)","72 (72,057,594,037,927,936 hosts)","73 (36,028,797,018,963,968 hosts)","74 (18,014,398,509,481,984 hosts)","75 (9,007,199,254,740,992 hosts)","76 (4,503,599,627,370,496 hosts)","77 (2,251,799,813,685,248 hosts)","78 (1,125,899,906,842,624 hosts)","79 (562,949,953,421,312 hosts)","80 (281,474,976,710,656 hosts)","81 (140,737,488,355,328 hosts)","82 (70,368,744,177,664 hosts)","83 (35,184,372,088,832 hosts)","84 (17,592,186,044,416 hosts)","85 (8,796,093,022,208 hosts)","86 (4,398,046,511,104 hosts)","87 (2,199,023,255,552 hosts)","88 (1,099,511,627,776 hosts)","89 (549,755,813,888 hosts)","90 (274,877,906,944 hosts)","91 (137,438,953,472 hosts)","92 (68,719,476,736 hosts)","93 (34,359,738,36 hosts)","94 (17,179,869,184 hosts)","95 (8,589,934,592 hosts)","96 (4,294,967,296 hosts)","97 (2,147,483,648 hosts)","98 (1,073,741,824 hosts)","99 (536,870,912 hosts)","100 (268,435,456 hosts)","101 (134,217,728 hosts)","102 (67,108,864 hosts)","103 (33,554,432 hosts)","104 (16,777,216 hosts)","105 (8,388,608 hosts)","106 (4,194,304 hosts)","107 (2,097,152 hosts)","108 (1,048,576 hosts)","109 (524,288 hosts)","110 (262,144 hosts)","111 (131,072 hosts)","112 (65,536 hosts)","113 (32,768 hosts)","114 (16,384 hosts)","115 (8,192 hosts)","116 (4,096 hosts)","117 (2,048 hosts)","118 (1,024 hosts)","119 (512 hosts)","120 (256 hosts)","121 (128 hosts)","122 (64 hosts)","123 (32 hosts)","124 (16 hosts)","125 (8 hosts)","126 (4 hosts)","127 (1 hosts)","128 (1 hosts)")
       j=1
       for(i=0;i<128;i++){
          document.calculate_form.BM.options[i].value=j
          document.calculate_form.BM.options[i].text=values_v6[i]
          document.calculate_form.BM.options[selected_index].selected = true
          document.calculate_form.BM.options[i].disabled=false
          j++
       }
//  document.forms.calculate_form.BM.options[selected_index].selected=true
 }
}
-->
</script>

<script language="JavaScript" type="text/javascript" charset="utf-8">
<!--
function calculate_red()
{
var IP=document.calculate_form.red.value;
var BM=document.calculate_form.BM.value;
var opciones="toolbar=no,scrollbars=1,right=100,top=100,width=475,height=550,resizable", i=0;
var URL="$server_proto://$base_uri/ip_calculatered.cgi?ip=" + IP + "&BM=" + BM; 
host_info=window.open(URL,"",opciones);
}
-->
</script>

<script language="JavaScript" type="text/javascript" charset="utf-8">
<!--
function change_BM_select(version,network_message,selected_index){
   var values_v4=new Array("CLASS A","255.0.0.0 - 16.777.214 hosts","255.128.0.0 - 8.388.606 hosts","255.192.0.0 - 4.194.302 hosts","255.224.0.0 - 2.097.150 hosts","255.240.0.0 - 1.048.574 hosts","255.248.0.0 - 524.286 hosts","255.252.0.0 - 262.142 hosts","255.254.0.0 - 131.070 hosts","CLASS B","255.255.0.0 - 65.534 hosts","255.255.128.0 - 32766 hosts","255.255.192.0 - 16.382 hosts","255.255.224.0 - 8.190 hosts","255.255.240.0 - 4.094 hosts","255.255.248.0 - 2.046 hosts","255.255.252.0 - 1.022 hosts","255.255.254.0 - 510 hosts","CLASS C","255.255.255.0 - 254 hosts","255.255.255.128 - 126 hosts","255.255.255.192 - 62 hosts","255.255.255.224 - 30 hosts","255.255.255.240 - 14 hosts","255.255.255.248 - 6 hosts","255.255.255.252 - 2 hosts","255.255.255.254 - 0 hosts","255.255.255.255 - 0 hosts")
    if (version == 'v4') {
       document.calculate_form.red.size='15'
       document.calculate_form.red.maxLength='40'
       document.calculate_form.ip_version[0].checked=true
       num_values = 28
       document.calculate_form.BM.length = num_values
       j=8
       for(i=0;i<28;i++){
          if ( i == '0' )
          {
             document.calculate_form.BM.options[i].text=values_v4[i]
             document.calculate_form.BM.options[i].disabled=true
          }
          else if ( i == '9' )
                   { 
             document.calculate_form.BM.options[i].text=values_v4[i]
             document.calculate_form.BM.options[i].disabled=true
                   } 
          else if ( i == '18' )
                   {
             document.calculate_form.BM.options[i].text=values_v4[i]
             document.calculate_form.BM.options[i].disabled=true
                   } 
          else {
            document.calculate_form.BM.options[i].text=j + ' (' + values_v4[i] + ')'
            document.calculate_form.BM.options[i].value=j
            document.calculate_form.BM.options[i].disabled=false
	    j++
          }
          if ( i == selected_index ) { 
             document.calculate_form.BM.options[i].selected = true
          }
       }
    }else{
       document.calculate_form.red.size='38'
       document.calculate_form.red.maxLength='40'
       document.calculate_form.ip_version[1].checked=true
       var values_v6=new Array("1 (9,223,372,036,854,775,808 " + network_message + ")","2 (4,611,686,018,427,387,904 " + network_message + ")","3 (2,305,843,009,213,693,952 " + network_message + ")","4 (1,152,921,504,606,846,976 " + network_message + ")","5 (576,460,752,303,423,488 " + network_message + ")","6 (288,230,376,151,711,744 " + network_message + ")","7 (144,115,188,075,855,872 " + network_message + ")","8 (72,057,594,037,927,936 " + network_message + ")","9 (36,028,797,018,963,968 " + network_message + ")","10 (18,014,398,509,481,984 " + network_message + ")","11 (9,007,199,254,740,992 " + network_message + ")","12 (4,503,599,627,370,496 " + network_message + ")","13 (2,251,799,813,685,248 " + network_message + ")","14 (1,125,899,906,842,624 " + network_message + ")","15 (562,949,953,421,312 " + network_message + ")","16 (281,474,976,710,656 " + network_message + ")","17 (140,737,488,355,328 " + network_message + ")","18 (70,368,744,177,664 " + network_message + ")","19 (35,184,372,088,832 " + network_message + ")","20 (17,592,186,044,416 " + network_message + ")","21 (8,796,093,022,208 " + network_message + ")","22 (4,398,046,511,104 " + network_message + ")","23 (2,199,023,255,552 " + network_message + ")","24 (1,099,511,627,776 " + network_message + ")","25 (549,755,813,888 " + network_message + ")","26 (274,877,906,944 " + network_message + ")","27 (137,438,953,472 " + network_message + ")","28 (68,719,476,736 " + network_message + ")","29 (34,359,738,36 " + network_message + ")","30 (17,179,869,184 " + network_message + ")","31 (8,589,934,592 " + network_message + ")","32 (4,294,967,296 " + network_message + ")","33 (2,147,483,648 " + network_message + ")","34 (1,073,741,824 " + network_message + ")","35 (536,870,912 " + network_message + ")","36 (268,435,456 " + network_message + ")","37 (134,217,728 " + network_message + ")","38 (67,108,864 " + network_message + ")","39 (33,554,432 " + network_message + ")","40 (16,777,216 " + network_message + ")","41 (8,388,608 " + network_message + ")","42 (4,194,304 " + network_message + ")","43 (2,097,152 " + network_message + ")","44 (1,048,576 " + network_message + ")","45 (524,288 " + network_message + ")","46 (262,144 " + network_message + ")","47 (131,072 " + network_message + ")","48 (65,536 " + network_message + ")","49 (32,768 " + network_message + ")","50 (16,384 " + network_message + ")","51 (8,192 " + network_message + ")","52 (4,096 " + network_message + ")","53 (2,048 " + network_message + ")","54 (1,024 " + network_message + ")","55 (512 " + network_message + ")","56 (256 " + network_message + ")","57 (128 " + network_message + ")","58 (64 " + network_message + ")","59 (32 " + network_message + ")","60 (16 " + network_message + ")","61 (8 " + network_message + ")","62 (4 " + network_message + ")","63 (2 " + network_message + ")","64 (18,446,744,073,709,551,616 hosts)","65 (9,223,372,036,854,775,808 hosts)","66 (4,611,686,018,427,387,904 hosts)","67 (2,305,843,009,213,693,952 hosts)","68 (1,152,921,504,606,846,976 hosts)","69 (576,460,752,303,423,488 hosts)","70 (288,230,376,151,711,744 hosts)","71 (144,115,188,075,855,872 hosts)","72 (72,057,594,037,927,936 hosts)","73 (36,028,797,018,963,968 hosts)","74 (18,014,398,509,481,984 hosts)","75 (9,007,199,254,740,992 hosts)","76 (4,503,599,627,370,496 hosts)","77 (2,251,799,813,685,248 hosts)","78 (1,125,899,906,842,624 hosts)","79 (562,949,953,421,312 hosts)","80 (281,474,976,710,656 hosts)","81 (140,737,488,355,328 hosts)","82 (70,368,744,177,664 hosts)","83 (35,184,372,088,832 hosts)","84 (17,592,186,044,416 hosts)","85 (8,796,093,022,208 hosts)","86 (4,398,046,511,104 hosts)","87 (2,199,023,255,552 hosts)","88 (1,099,511,627,776 hosts)","89 (549,755,813,888 hosts)","90 (274,877,906,944 hosts)","91 (137,438,953,472 hosts)","92 (68,719,476,736 hosts)","93 (34,359,738,36 hosts)","94 (17,179,869,184 hosts)","95 (8,589,934,592 hosts)","96 (4,294,967,296 hosts)","97 (2,147,483,648 hosts)","98 (1,073,741,824 hosts)","99 (536,870,912 hosts)","100 (268,435,456 hosts)","101 (134,217,728 hosts)","102 (67,108,864 hosts)","103 (33,554,432 hosts)","104 (16,777,216 hosts)","105 (8,388,608 hosts)","106 (4,194,304 hosts)","107 (2,097,152 hosts)","108 (1,048,576 hosts)","109 (524,288 hosts)","110 (262,144 hosts)","111 (131,072 hosts)","112 (65,536 hosts)","113 (32,768 hosts)","114 (16,384 hosts)","115 (8,192 hosts)","116 (4,096 hosts)","117 (2,048 hosts)","118 (1,024 hosts)","119 (512 hosts)","120 (256 hosts)","121 (128 hosts)","122 (64 hosts)","123 (32 hosts)","124 (16 hosts)","125 (8 hosts)","126 (4 hosts)","127 (1 hosts)","128 (1 hosts)")
       num_values = '129'
       document.calculate_form.BM.length = num_values
       j=1
       for(i=0;i<128;i++){
          document.calculate_form.BM.options[i].value=j
          document.calculate_form.BM.options[i].text=values_v6[i]
          document.calculate_form.BM.options[selected_index].selected = true
          document.calculate_form.BM.options[i].disabled=false
          j++
       }
    }
}
-->
</script>


<script language="JavaScript" type="text/javascript" charset="utf-8">
<!--
function create_hidden_selected_index(){
  var selIndex = document.calculate_form.BM.selectedIndex;
  document.getElementById('selected_index').innerHTML = '<input type=\"hidden\" name=\"selected_index\" value=\"' + selIndex + '\">';
}
-->
</script>
<div id="CalcBox">

EOF
#print 	STDERR "TEST: RED: $red\n";

print "<p><form name=\"calculate_form\" id=\"calculate_form\" method=\"POST\" action=\"$server_proto://$base_uri/ip_calculatered.cgi\">\n";
print "<table border=\"0\" cellpadding=\"2\">";
print "<tr><td></td><td>IPv4<input type=\"radio\" name=\"ip_version\" value=\"v4\" onchange=\"change_BM_select('v4',\'$$lang_vars{entradas_redes_message}\','19');\" checked> IPv6<input type=\"radio\" name=\"ip_version\" value=\"v6\" onchange=\"change_BM_select('v6',\'$$lang_vars{entradas_redes_message}\','119');\"><span id=\"selected_index\"></span></td></tr>\n";

print "<tr><td class=\"table_text\" nowrap>$$lang_vars{ip_address_message}</td>\n";
print "<td colspan=\"2\"><input name=\"red\" id=\"red\" type=\"text\" size=\"20\" maxlength=\"40\" value=\"$red\"></td></tr>";
print "<tr><td class=\"table_text\">$$lang_vars{BM_message}</td>\n";
print "<td><select name=\"BM\" size=\"1\" style=\"width:17em\">\n";


my $bm_i_message;
$BM =~ /^(\d{1,2})/;
my $BM_select=$1 || "";
for (my $i = 8; $i < 33; $i++) {
	print "<option disabled>CLASS A</option>" if $i == "8";
	print "<option disabled>CLASS B</option>" if $i == "16";
	print "<option disabled>CLASS C</option>" if $i == "24";
        if ( $i =~ /^\d$/ ) {
                $bm_i_message = "bm_0" . $i . "_message";
        } else {
                $bm_i_message = "bm_" . $i . "_message";
        }
        if ( $i == $BM_select ) {
                print "<option selected>$i ($$lang_vars{$bm_i_message})</option>";
        } else {
                print "<option >$i ($$lang_vars{$bm_i_message})</option>";
        }
}
print "</select></td><td>&nbsp;&nbsp;<input type=\"submit\" value=\"$$lang_vars{calcular_message}\" name=\"B2\" class=\"input_link_w_net\" onclick=\"create_hidden_selected_index();\"></td></tr></table>\n";
print "</form>\n";

if ( ! $red ) {
print "</div>\n";
#print "<p><br>\n";
print "</div>\n";
print "</body>\n";
print "</html>\n";
exit 0;
}

#print STDERR "TEST: $red/$BM\n";
my $redob = "$red/$BM";

my ($ipob_red,$address_32);
$ipob_red = new Net::IP ($redob);
if ( ! $ipob_red && $ip_version eq "v4" ) {
	my $BM_32 = "32";
	$redob = "$red/$BM_32";
	$ipob_red = new Net::IP ($redob) || die "Can not create ip object $redob: $!\n";
	$address_32="1";	
} elsif ( ! $ipob_red ) {
	my $BM_128 = "128";
	$redob = "$red/$BM_128";
	$ipob_red = new Net::IP ($redob) || die "Can not create ip object $redob: $!\n";
	$address_32="1";	
}

my $ip_int=($ipob_red->intip());

my ( $netmask_in, $binmask_in, $class);
if ( $ip_version eq "v4" ) {
	if ( $BM =~ /^(\d\d).*/ && ! $ENV{'QUERY_STRING'} ) {
		$BM =~ /^(\d\d).+\((\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).+/;
		$BM = $1;
		$netmask_in = $2;
	} else {
		if ( $BM =~ /^(\d\d).*/ ) {
			$BM =~ /^(\d\d).+\((\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).+/;
			$BM = $1;
			$netmask_in = $2;
		} elsif ( $BM =~ /^(\d).+/ ) {
			$BM =~ /^(\d).+\((\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).+/;
			$BM = $1;
			$netmask_in = $2;
		}
	}

	$netmask_in =~ /(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})/;
	my $first_mask_oc = $1;
	my $sec_mask_oc = $2;
	my $thi_mask_oc = $3;
	my $fou_mask_oc = $4;
	my $first_mask_oc_bin=dec2bin("$first_mask_oc");
	my $sec_mask_oc_bin=dec2bin("$sec_mask_oc");
	my $thi_mask_oc_bin=dec2bin("$thi_mask_oc");
	my $fou_mask_oc_bin=dec2bin("$fou_mask_oc");

	$binmask_in = "$first_mask_oc_bin" . "$sec_mask_oc_bin" . "$thi_mask_oc_bin" . "$fou_mask_oc_bin";
	my $len_first = length($first_mask_oc_bin);
	my $len_sec = length($sec_mask_oc_bin);
	my $len_thi = length($thi_mask_oc_bin);
	my $len_fou = length($fou_mask_oc_bin);
	my $len_falta;
	if ( $len_first < 8 ) { 
		$len_falta=8-$len_first; 
		$first_mask_oc_bin = "$first_mask_oc_bin" . 0 x $len_falta;
	}
	if ( $len_sec < 8 ) { 
		$len_falta=8-$len_sec; 
		$sec_mask_oc_bin = "$sec_mask_oc_bin" . 0 x $len_falta;
	}
	if ( $len_thi < 8 ) { 
		$len_falta=8-$len_thi; 
		$thi_mask_oc_bin = "$thi_mask_oc_bin" . 0 x $len_falta;
	}
	if ( $len_fou < 8 ) { 
		$len_falta=8 - $len_fou; 
		$fou_mask_oc_bin = "$fou_mask_oc_bin" . 0 x $len_falta;
	}
	$binmask_in = "$first_mask_oc_bin" . "$sec_mask_oc_bin" . "$thi_mask_oc_bin" . "$fou_mask_oc_bin";

	if ( $ip_int <= 2147483647 ) {
		$class = "A";
	} elsif ( $ip_int >= 2147483648 && $ip_int <= 3221225471 ) {
		$class = "B";
	} elsif ( $ip_int >= 3221225472 && $ip_int <= 3758096383 ) {
		$class = "C";
	} elsif ( $ip_int >= 3758096384 && $ip_int <= 4160749567 ) {
		$class = "D";
	} else {
		$class = "E";
	}
}

$netmask_in=($ipob_red->mask()) if ! $netmask_in;
my $type=($ipob_red->iptype());
my $hexip=($ipob_red->hexip());
my $hex = unpack('H*', "$red"); 
my $bin=($ipob_red->binip());
my $short=($ipob_red->short());
$short=$short . "/" . $BM;

my ($red_in,$red_in_bin,$nibbles,$nibbles_red,$rest);
if ( $address_32 ) {
	my $binmask=($ipob_red->binmask());
	if ( $ip_version eq "v4" ) {
		$red_in_bin = $binmask_in & $bin;
		$red_in_bin =~ /([01]{8})([01]{8})([01]{8})([01]{8})/;
		my $red_in_bin_first_oc=$1;
		my $red_in_bin_sec_oc=$2;
		my $red_in_bin_thi_oc=$3;
		my $red_in_bin_fou_oc=$4;
		my $red_in_first = bin2dec("$red_in_bin_first_oc");
		my $red_in_sec = bin2dec("$red_in_bin_sec_oc");
		my $red_in_thi = bin2dec("$red_in_bin_thi_oc");
		my $red_in_fou = bin2dec("$red_in_bin_fou_oc");
		$red_in = $red_in_first . "." . $red_in_sec . "." . $red_in_thi . "." . $red_in_fou;
	} else {
		$binmask_in= "";
		for (my $i = 1; $i <= $BM; $i++) {
			$binmask_in = $binmask_in . "1";
		}
		$rest=128-$BM;
		for (my $i=1;$i<=$rest;$i++) {
			$binmask_in = $binmask_in . "0";
		}
		$red_in_bin = $binmask_in & $bin;
		$red_in=ip_bintoip ($red_in_bin,6);
	}
}

my $red_orig_show="";
if ( $ip_version eq "v6" ) {
	my $red_exp= ip_expand_address ($red,6);
	my $nibbles_pre=$red_exp;
	$nibbles_pre =~ s/://g;
	my @nibbles=split(//,$nibbles_pre);
	my @nibbles_reverse=reverse @nibbles;
	$nibbles="";
	$rest=128-$BM;
	my $red_part_helper = ($rest+1)/4;
	$red_part_helper = ceil($red_part_helper);
	my $i=1;
	foreach my $num (@nibbles_reverse ) {
		if ( $i==$red_part_helper && $nibbles =~ /\w/) {
			$nibbles = "<span style=\"color: blue;\">". $nibbles . "." . $num . "</span>";
		} elsif ( $i==$red_part_helper && $nibbles eq "") {
			$nibbles = "<span style=\"color: blue;\">". $num . "</span>";
		} elsif ( $nibbles =~ /\w/) {
			$nibbles .= "." . $num;
		} else {
			$nibbles = $num;
		}
		$i++;
	}
	$nibbles .= ".ip6.arpa.";

	my $red_part_helper1 = ($BM-1)/4;
	$red_part_helper1 = int($red_part_helper1);
	$red_exp="";
	$red_part_helper = 32 - $red_part_helper;
	$i=0;
	foreach my $nib (@nibbles ) {
		if ( $i == 4 || $i==8 || $i==12 || $i==16 || $i==20 || $i==24 || $i==28 ) {
			$red_exp .= ":";
		}
		if ( $i==$red_part_helper1 ) {
			$red_exp .= "<span style=\"color: blue;\">" . $nib;
		} else {
			$red_exp .= $nib;
		}
		$i++;
	}
	$red_exp .= "</span>";
	$red_orig_show = $red_exp;
} else {
	$red_orig_show = $red_orig;
}


$red = $red_in if $red_in;


my $redob_in = $red . "/" . $BM;
my $ipob_red_in = new Net::IP ($redob_in) or die "Can not create IP object: $!\n";;
my $redint=($ipob_red_in->intip());
my $broadcast=($ipob_red_in->last_ip());
my $first_ip_int=$redint+1;
my $first_ip = $gip->int_to_ip("$client_id","$first_ip_int","$ip_version");
my $last_ip_int = ($ipob_red_in->last_int());
my $ip_total=$last_ip_int-$first_ip_int;
$last_ip_int--;
my $last_ip = $gip->int_to_ip("$client_id","$last_ip_int","$ip_version");
my ($v6,$wildcard);
my $embedded_ipv4="";
if ( $ip_version eq "v4" ) {
	$netmask_in =~ /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/;
	my $first_oc_wi = 255 - $1;
	my $sec_oc_wi = 255 - $2;
	my $thi_oc_wi = 255 - $3;
	my $fou_oc_wi = 255 - $4;
	$wildcard = $first_oc_wi . "." . "$sec_oc_wi" . "." . $thi_oc_wi . "." . $fou_oc_wi;
	$hexip =~ /.x(.*)/;
	$v6=$1;
	my $length_v6=length($v6);
	$v6 = "0" . "$v6" if $length_v6 == 7;
	$v6 =~ /(.{4})(.{4})/;
	$v6="::ffff:" .  $1 . ":" . $2;
} else {
#	$embedded_ipv4 = ip_get_embedded_ipv4($red);
}

print "<script type=\"text/javascript\">\n";
print "document.calculate_form.red.focus();\n";
print "</script>\n";
print "<p><table border=\"0\" cellpadding=\"2\">";
print "<tr><td nowrap>$$lang_vars{ip_address_message}</td><td><b>$red_orig_show</b></td></tr>\n";
print "<tr><td nowrap>$$lang_vars{clase_message}</td><td><b>$class</b></td></tr>\n" if $ip_version eq "v4";
print "<tr><td nowrap>$$lang_vars{tipo_message}</td><td><b>$type</b></td></tr>\n";
print "<tr><td nowrap>$$lang_vars{redes_message}</td><td><b>$red</b></td></tr>\n";
print "<tr><td nowrap>$$lang_vars{bitmask_message}</td><td><b>$BM</b></td></tr>\n";
print "<tr><td nowrap>$$lang_vars{netmask_message}</td><td><b>$netmask_in</b></td></tr>\n" if $ip_version eq "v4";
print "<tr><td nowrap>$$lang_vars{wildcardmask_message}</td><td><b>$wildcard</b></td></tr>\n" if $ip_version eq "v4";
if ((( $BM == "31" || $BM =="32" && $ip_version eq "v4" )) || (( $BM == "127" || $BM =="128" && $ip_version eq "v6" ))) {
	print "<tr><td>$$lang_vars{host_range_message}</td><td><b>N/A</b></td></tr>\n";
} else {
	print "<tr><td>$$lang_vars{host_range_message}</td><td><b>$first_ip-<br>$last_ip</b></td></tr>\n";
}
print "<tr><td nowrap>$$lang_vars{broadcast_message}</td><td><b>$broadcast</b></td></tr>\n";
if ((( $BM == "31" || $BM =="32" && $ip_version eq "v4" )) || (( $BM == "127" || $BM =="128" && $ip_version eq "v6" ))) {
	print "<tr><td>$$lang_vars{ip_en_total_message}</td><td><b>0</b></td></tr>\n";
} else {
	print "<tr><td>$$lang_vars{ip_en_total_message}</td><td><b>$ip_total</b></td></tr>\n";
}

print "<tr><td><br></td></tr>\n";
print "<tr><td nowrap>$$lang_vars{corto_message}</td><td><b>$short</b></td></tr>\n";
print "<tr><td nowrap>$$lang_vars{int_id_message}</td><td><b>$ip_int</b></td></tr>\n";
print "<tr><td nowrap>$$lang_vars{hex_id_message} I </td><td><b>$hexip</b></td></tr>\n";
print "<tr><td nowrap>$$lang_vars{hex_id_message} II</td><td><b>$hex</b></td></tr>\n";
print "<tr><td nowrap>$$lang_vars{bin_id_message}</td><td><b>$bin</b></td></tr>\n";
print "<tr><td nowrap>$$lang_vars{ipv6_arpa_format_message}<br>(Hostteil . Netzteil)</td><td><b>$nibbles</b></td></tr>\n" if $ip_version eq "v6";
#print "<tr><td nowrap>$$lang_vars{ipv6_arpa_format_message}</td><td><b>$nibbles_red</b></td></tr>\n" if $ip_version eq "v6";
print "<tr><td nowrap>$$lang_vars{mapeada_message}</td><td><b>$v6</b></td></tr>\n" if $ip_version eq "v4";
#print "<tr><td nowrap>$$lang_vars{embedded_ipv4_message}</td><td><b> $red - $embedded_ipv4</b></td></tr>\n" if $ip_version eq "v6" && $embedded_ipv4;
print "</table><p>\n";


print "<span class=\"close_window\" onClick=\"window.close()\" style=\"cursor:pointer;\"> $$lang_vars{close_message} </span>";

print "</div>\n";
#print "<p><br>\n";
print "</div>\n";
print "</body>\n";
print "</html>\n";
exit 0;


### subroutines

sub dec2bin {
    my $str = unpack("B32", pack("N", shift));
    $str =~ s/^0+(?=\d)//;   # otherwise you'll get leading zeros
    return $str;
}
sub bin2dec {
    return unpack("N", pack("B32", substr("0" x 32 . shift, -32)));
}
