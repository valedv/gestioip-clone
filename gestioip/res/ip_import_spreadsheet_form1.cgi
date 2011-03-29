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
use Cwd;
use CGI;
use CGI qw/:standard/;
use CGI::Carp qw ( fatalsToBrowser );
use File::Basename;


my $gip = GestioIP -> new();

my $base_uri = $gip->get_base_uri();
my $server_proto=$gip->get_server_proto();

my $lang = "";
my ($lang_vars,$vars_file)=$gip->get_lang("","$lang");

my %daten=();

my $query = new CGI;
my $client_id = $query->param("client_id") || $gip->get_first_client_id();
if ( $client_id !~ /^\d{1,4}$/ ) {
	$client_id = 1;
	$gip->CheckInput("$client_id",\%daten,"$$lang_vars{mal_signo_error_message}","$$lang_vars{redes_message}","$vars_file");
	$gip->print_error("$client_id","$$lang_vars{formato_malo_message}");
}

$gip->CheckInput("$client_id",\%daten,"$$lang_vars{mal_signo_error_message}","$$lang_vars{import_sheet_message}","$vars_file");

my $module = "Spreadsheet::ParseExcel";
my $module_check=$gip->check_module("$module") || "0";
$gip->print_error("$client_id","$$lang_vars{no_spreadsheet_support}") if $module_check != "1";

my @global_config = $gip->get_global_config("$client_id");
my $ipv4_only_mode=$global_config[0]->[5] || "yes";

my $import_dir = getcwd;
$import_dir =~ s/res.*/import/;


$CGI::POST_MAX = 1024 * 5000;
my $safe_filename_characters = "a-zA-Z0-9_.-";
my $upload_dir = getcwd;
$upload_dir =~ s/res.*/import/;


my $filename = $query->param("spreadsheet");

$gip->print_error("$client_id","$$lang_vars{no_excel_name_message}") if ( !$filename );

my ( $name, $path, $extension ) = fileparse ( $filename, '\..*' );
$filename = $name . $extension;
$filename =~ tr/ /_/;
$filename =~ s/[^$safe_filename_characters]//g;

if ( $filename =~ /^([$safe_filename_characters]+)$/ ) {
	$filename = $1;
} else {
	$gip->print_error("$client_id","$$lang_vars{formato_malo_message}");
}

$gip->print_error("$client_id","$$lang_vars{no_xls_extension_message}") if $filename !~ /\.xls$/;

my $upload_filehandle = $query->upload("spreadsheet");
if ( $upload_dir =~ /^(\/.*)$/ ) {
        $upload_dir =~ /^(\/.*)$/;
        $upload_dir = $1;
}

open ( UPLOADFILE, ">$upload_dir/$filename" ) or die "Can not open $upload_dir/$filename: $!";
binmode UPLOADFILE;

while ( <$upload_filehandle> ) {
	print UPLOADFILE;
}

close UPLOADFILE;

my @cc_values=$gip->get_custom_columns("$client_id");


print "<p>\n";
print "<b>$$lang_vars{step_two_message}</b> <a href=\"$server_proto://$base_uri/help.html#import_spreadsheet\" target=\"_blank\" class=\"help_link_link\"><span class=\"help_link\">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</a>\n";
print "<p><br>\n";
print "<p>$$lang_vars{sheet_step_two_message}<br>\n";
print "<p>";
print "<table border=\"0\" cellpadding=\"7\">\n";
print "<tr><td><form  method=\"POST\" action=\"$server_proto://$base_uri/res/ip_import_spreadsheet.cgi\">$$lang_vars{all_sheets_message}</td><td> <input type=\"radio\" name=\"sheet_import_type\" value=\"all_sheet\" onclick=\"hoja.disabled=true;some_sheet_values.disabled=true;hoja.value = '';some_sheet_values.value = ''\" checked></td></tr>\n";
print "<tr><td>$$lang_vars{sheet_name_message}</td><td> <input type=\"radio\" name=\"sheet_import_type\" value=\"one_sheet\" onclick=\"hoja.disabled=false;some_sheet_values.disabled=true;some_sheet_values.value = ''\"> <input name=\"hoja\" type=\"text\" size=\"12\" maxlength=\"50\" disabled></td></tr>\n";
print "<tr><td>$$lang_vars{sheets_message}</td><td> <input type=\"radio\" name=\"sheet_import_type\" value=\"some_sheet\" onclick=\"hoja.disabled=true;some_sheet_values.disabled=false;hoja.value = ''\"> <input name=\"some_sheet_values\" type=\"text\" size=\"12\" maxlength=\"30\" disabled> <img src=\"../imagenes/quick_help.png\" title=\"$$lang_vars{sheets_explic_message}\">\n";
print "</td></tr></table><p>\n";

if ( $ipv4_only_mode ne "yes" ) {
print "<br>$$lang_vars{choose_ip_version_redes_message}<br>\n";
print <<EOF;
<p>
<table border="0">
<tr><td align="right">$$lang_vars{ip_version_message}</td>
        <td colspan="3">&nbsp;&nbsp;&nbsp;v4<input type="radio" name="ip_version" value="v4" checked>&nbsp;&nbsp;&nbsp;v6<input type="radio" name="ip_version" value="v6"></td></tr>
</table>
<br>
EOF
}

print "<p><br>$$lang_vars{correpondig_colums_message}<p>\n";
print "<table border=\"0\" cellpadding=\"5\">\n";
print "<tr><td><b>$$lang_vars{columna_message}</b></td><td><b>$$lang_vars{entradas_message}</b></td></tr>\n";
print "<tr><td><select name=\"redes\" size=\"1\" onclick=\"mixed.value = '';\">";
my @nums=("","A","B","C","D","E","F","G","H","I","J","K","L");
foreach (@nums) {
	print "<option>$_</option>\n";
}
print "</select>\n";
print "</td><td>$$lang_vars{redes1_message}</td></tr>\n";
print "<tr><td><select name=\"BM\" size=\"1\" onclick=\"mixed.value = '';\">";
foreach (@nums) {
	print "<option>$_</option>\n";
}
print "</select>\n";
print "</td><td>$$lang_vars{bit_o_subnetmask_message}</td></tr>\n";
print "<tr><td><b><i>$$lang_vars{o_message}</b></i>\n";
print "</td><td></td></tr>\n";
print "<tr><td><select name=\"mixed\" size=\"1\" onclick=\"redes.value = '';BM.value = '';\">";
foreach (@nums) {
	print "<option>$_</option>\n";
}
print "</select>\n";
print "</td><td>$$lang_vars{mixed_bit_y_subnetmask_message}</td></tr>\n";
print "<tr><td colspan=\"2\"><br><i>$$lang_vars{columnas_opcionales_message}</i></td></tr>\n";
print "<tr><td><select name=\"descr\" size=\"1\">";
foreach (@nums) {
	print "<option>$_</option>\n";
}
print "</select>\n";
print "</td><td>$$lang_vars{description_message}</td></tr>\n";
print "<tr><td><select name=\"loc\" size=\"1\">";
foreach (@nums) {
	print "<option>$_</option>\n";
}
print "</select>\n";
print "</td><td>$$lang_vars{loc_message}</td></tr>\n";
print "<tr><td><select name=\"cat\" size=\"1\">";
foreach (@nums) {
	print "<option>$_</option>\n";
}
print "</select>\n";
print "</td><td>$$lang_vars{cat_message}</td></tr>\n";
print "<tr><td><select name=\"comentario\" size=\"1\">";
foreach (@nums) {
	print "<option>$_</option>\n";
}
print "</select>\n";
print "</td><td>$$lang_vars{comentario_message}</td></tr>\n";

#if ( scalar(@cc_values) > 0 ) {
#        print "<tr><td colspan=\"2\"><br><i>$$lang_vars{custom_column_message}</i></td></tr>\n";
#}
print "<tr><td colspan=\"2\"><br></td></tr>\n";
for ( my $k = 0; $k < scalar(@cc_values); $k++ ) {
	if ( $cc_values[$k]->[0] ne "vlan" ) {
		print "<tr><td><select name=\"$cc_values[$k]->[0]\" size=\"1\">";
		foreach (@nums) {
			print "<option>$_</option>\n";
		}
		print "</select>\n";
		print "</td><td>\n";
		print "$cc_values[$k]->[0]</td></tr>";
	}
}


print "<tr><td><p><br><input type=\"checkbox\" name=\"mark_sync\" value=\"y\" checked></td><td><p><br>$$lang_vars{mark_sync_message}</td></tr>\n";


print "<tr><td colspan=\"2\"><br><input name=\"spreadsheet\" type=\"hidden\" value=\"$filename\"><input type=\"hidden\" name=\"client_id\" value=\"$client_id\"><input type=\"submit\" value=\"$$lang_vars{importar_message}\" name=\"B1\" class=\"input_link_w\"></td></tr>\n";
print "</form>\n";
print "</table>\n";

$gip->print_end("$client_id");
