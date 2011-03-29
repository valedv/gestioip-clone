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

my $daten=<STDIN>;
my $gip = GestioIP -> new();
my %daten=$gip->preparer("$daten") if $daten;

my $lang = $daten{'lang'} || "";
my ($lang_vars,$vars_file,$entries_per_page)=$gip->get_lang("","$lang");
my $base_uri = $gip->get_base_uri();

my $client_id = $daten{'client_id'} || $gip->get_first_client_id();
my $server_proto=$gip->get_server_proto();

my $ip_version_ele = $daten{'ip_version_ele'} || "";

$gip->CheckInput("$client_id",\%daten,"$$lang_vars{mal_signo_error_message}","$$lang_vars{statistics_message}","$vars_file");

$gip->print_error("$client_id","$$lang_vars{formato_malo_message} (version_ele)") if $ip_version_ele !~ /^(v4|v6|46)$/;

my $stat_type=$daten{stat_type};
$gip->print_error("$client_id",$$lang_vars{formato_malo_message}) if $stat_type !~ /^percent_network_bigger|percent_network_smaller|percent_range_bigger|percent_range_smaller$/;
my $percent_usage = $daten{percent_usage};
$gip->print_error("$client_id",$$lang_vars{formato_malo_message}) if $percent_usage !~ /^\d{1,2}$/;
$percent_usage = $percent_usage . ".0";
my $filter=$daten{filter};

my (@stat_host_all_red, @all_red_nums);
if ( $stat_type eq "percent_network_smaller" || $stat_type eq "percent_network_bigger" ) {
	if ( $filter ) {
		@stat_host_all_red = $gip->get_stat_host_all_red("$client_id","$filter");
		if ( $stat_type eq "percent_network_smaller" ) {
			@all_red_nums = $gip->get_stat_all_red_nums("$client_id","$filter");
		}
	} else {
		@stat_host_all_red = $gip->get_stat_host_all_red("$client_id");
		if ( $stat_type eq "percent_network_smaller" ) {
			@all_red_nums = $gip->get_stat_all_red_nums("$client_id");
		}
	}
}


if ( $stat_type eq "percent_range_smaller" || $stat_type eq "percent_range_bigger" ) {
	@stat_host_all_red = $gip->get_stat_host_all_range("$client_id");
	if ( $stat_type eq "percent_range_smaller" ) {
		@all_red_nums = $gip->get_stat_all_range_nums("$client_id");
	}
}
	
my $i=0;
my %counts = ();
for (@stat_host_all_red) {
        $counts{$stat_host_all_red[$i++]->[0]}++;
}

$i=0;
if ( $stat_type eq "percent_network_smaller" || $stat_type eq "percent_range_smaller") {
	for (@all_red_nums) {
		$counts{$all_red_nums[$i]->[0]} = "0" if ! $counts{$all_red_nums[$i]->[0]};
		$i++;
	}
}

if ( ! %counts ) {
	print "<p class=\"NotifyText\">$$lang_vars{no_resultado_message}</p><br>\n";
	print "<p><FORM><INPUT TYPE=\"BUTTON\" VALUE=\"$$lang_vars{atras_message}\" ONCLICK=\"history.go(-1)\" class=\"error_back_link\"></FORM>\n";
	$gip->print_end("$client_id");
}


if ( $stat_type eq "percent_network_smaller" || $stat_type eq "percent_network_bigger" ) {
	if ( $stat_type eq "percent_network_bigger" ) {
		print "<p><b>$$lang_vars{network_usage_message} > ${percent_usage}%</b><p>\n";
	} else {
		print "<p><b>$$lang_vars{network_usage_message} < ${percent_usage}%</b><p>\n";
	}
	my %redes = $gip->get_redes_stat_hash("$client_id");
	my %anz_hosts_bm = $gip->get_anz_hosts_bm_hash("$client_id");
	print "<p>\n";
	print "<table border=\"0\" style=\"border-collapse:collapse\" cellpadding=\"2\">\n";
	print "<tr><td><b>$$lang_vars{percent_usage_message}</b></td><td><b>&nbsp;&nbsp;&nbsp;$$lang_vars{redes_message}</b></td><td>&nbsp;&nbsp;&nbsp;<b>$$lang_vars{BM_message}</bm></td><td><b>&nbsp;&nbsp;&nbsp;$$lang_vars{description_message}</b></td><td><b>&nbsp;&nbsp;&nbsp;$$lang_vars{loc_message} </b></td><td><b>&nbsp;&nbsp;&nbsp;$$lang_vars{cat_message} </b></td><td><b>&nbsp;&nbsp;&nbsp;$$lang_vars{comentario_message} </b></td><td></td></tr>\n";
	my $j="0";
	my $color_helper="0";
	my ( $red_num,$color,$stylename);
	my ( $keys, $value );
	my $found = "0";
	foreach $keys (sort {$a <=> $b} keys %counts) {
		$red_num = "$keys";
		$value = $counts{$keys};
		my $red = $redes{"$keys"};
		$red =~ /^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\/(\d{1,2}):/;
		my $BM_red = $1;
		my $anz_total = $anz_hosts_bm{"$BM_red"};
		$anz_total = $anz_total - 2;

		my $anz_total_show = $anz_total;
		my $ocu_show = $value;
		my $ocu = $value . ".001";
		$anz_total = $anz_total . ".000";
		my $percent_ocu;
		if ( $ocu eq "0.001" ) {
			$percent_ocu = "0";
		} else {
			$percent_ocu=100*$ocu/$anz_total;
			$percent_ocu =~ /^(\d+\.\d?).*/;
			$percent_ocu = $1;
			$percent_ocu = "100" if $percent_ocu eq "100.0";
		}
		$red =~ /^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\/\d{1,2}):X-X:(.*):X-X:(.*):X-X:(.*):X-X:(.*)/;
		my $ip = $1;
		my $desc = $2 || "---";
		$desc = "---" if $desc eq "NULL";
		my $cat = $3 || "---";
		$cat = "---" if $cat eq "NULL";
		my $loc = $4 || "---";
		$loc = "---" if $loc eq "NULL";
		my $comentario = $5 || "---";
		$comentario = "---" if $comentario eq "NULL";



		my $form_name = "document.forms.list_host" . $j . ".submit()";
		$stylename="show_detail";

		$ip =~ /^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\/(\d{1,2})/;
		my $red_show = $1;
		my $BM_show = $2;

		my $ocu_color;
		if ( $stat_type eq "percent_network_bigger" ) {
			if ( $percent_ocu >= $percent_usage ) {
				if ( $color_helper eq "0" ) {
					$color="#f2f2f2";
					$color_helper="1";
				} else {
					$color="white";
					$color_helper="0";
				}
				if ( $percent_ocu >= 90 ) {
					$ocu_color = "red";
				} elsif ( $percent_ocu >= 80 ) {
					$ocu_color = "darkorange";
				} else {
					$ocu_color = "green";
				}

				print "<tr bgcolor=\"$color\" class=\"$stylename\" onClick=\"$form_name\" style=\"cursor:pointer;\"><td nowrap><font color=\"$ocu_color\"><b>$percent_ocu%</b></font> ($ocu_show/$anz_total_show)</td><td>&nbsp;&nbsp;&nbsp;$red_show</td><td>&nbsp;&nbsp;&nbsp;$BM_show</td><td>&nbsp;&nbsp;&nbsp;$desc</td><td>&nbsp;&nbsp;&nbsp;$loc</td><td>&nbsp;&nbsp;&nbsp;$cat</td><td>&nbsp;&nbsp;&nbsp;$comentario</td><td><form method=\"POST\" name=\"list_host$j\" action=\"$server_proto://$base_uri/ip_show.cgi\"><input name=\"red_num\" type=\"hidden\" value=\"$red_num\"><input name=\"client_id\" type=\"hidden\" value=\"$client_id\"></form></td></tr>";
			$found = "1";
			}
		} elsif (  $stat_type eq "percent_network_smaller" ) {
			if ( $percent_ocu < $percent_usage ) {
				if ( $color_helper eq "0" ) {
					$color="#f2f2f2";
					$color_helper="1";
				} else {
					$color="white";
					$color_helper="0";
				}
				if ( $percent_ocu >= 90 ) {
					$ocu_color = "red";
				} elsif ( $percent_ocu >= 80 ) {
					$ocu_color = "darkorange";
				} else {
					$ocu_color = "green";
				}
				print "<tr bgcolor=\"$color\" class=\"$stylename\" onClick=\"$form_name\" style=\"cursor:pointer;\"><td nowrap><font color=\"$ocu_color\"><b>$percent_ocu%</b></font> ($ocu_show/$anz_total_show)</td><td>&nbsp;&nbsp;&nbsp;$red_show</td><td>&nbsp;&nbsp;&nbsp;$BM_show</td><td>&nbsp;&nbsp;&nbsp;$desc</td><td>&nbsp;&nbsp;&nbsp;$loc</td><td>&nbsp;&nbsp;&nbsp;$cat</td><td>&nbsp;&nbsp;&nbsp;$comentario</td><td><form method=\"POST\" name=\"list_host$j\" action=\"$server_proto://$base_uri/ip_show.cgi\"><input name=\"red_num\" type=\"hidden\" value=\"$red_num\"><input name=\"client_id\" type=\"hidden\" value=\"$client_id\"></form></td></tr>";
			$found = "1";
			}
		}
		$j++;
	}
	print "</table>\n";
	if ( $found != "1" ) {
		print "<p class=\"NotifyText\">$$lang_vars{no_resultado_message}</p><br>\n";
		print "<p><FORM><INPUT TYPE=\"BUTTON\" VALUE=\"$$lang_vars{atras_message}\" ONCLICK=\"history.go(-1)\" class=\"error_back_link\"></FORM>\n";
		$gip->print_end("$client_id");
	}

} else {

	if ( $stat_type eq "percent_range_bigger" ) {
		print "<p><b>$$lang_vars{range_usage_message} > ${percent_usage}%</b><p>\n";
	} else {
		print "<p><b>$$lang_vars{range_usage_message} < ${percent_usage}%</b><p>\n";
	}
	my %ranges = $gip->get_ranges_stat_hash("$client_id");
	print "<p>\n";
	print "<table border=\"0\" style=\"border-collapse:collapse\" cellpadding=\"2\">\n";
	print "<tr><td><b>$$lang_vars{percent_usage_message}</b></td><td><b>&nbsp;&nbsp;&nbsp;$$lang_vars{redes_message}</b></td><td>&nbsp;&nbsp;&nbsp;<b>RANGE</bm></td><td><b>&nbsp;&nbsp;&nbsp;$$lang_vars{comentario_message}</b></td><td><b>&nbsp;&nbsp;&nbsp;$$lang_vars{range_type_message} </b></td><td></td></tr>\n";
	my $j="0";
	my $color_helper="0";
	my ( $red_num,$color,$stylename);
	my ( $keys, $value );
	my $found = "0";
	foreach $keys (sort {$a <=> $b} keys %counts) {
		my $range_num = "$keys";
		$value = $counts{$keys};
		my $range = $ranges{"$keys"};

		$range =~ /^(.*):X-X:(.*):X-X:(.*):X-X:(.*):X-X:(.*):X-X:(.*)/;
		my $start_ip_int = $1;
		my $end_ip_int = $2;
		my $start_ip = $gip->int_to_ip("$client_id","$start_ip_int");
		my $end_ip = $gip->int_to_ip("$client_id","$end_ip_int");
		my $comentario = $3 || "---";
		$comentario = "---" if $comentario eq "NULL";
		my $range_type = $4 || "---";
		$range_type = "---" if $range_type eq "NULL";
		my $red_num = $5;
		my $red_ip = $6;
		my $anz_total = $end_ip_int - $start_ip_int;
		my $anz_total_show = $anz_total;
		my $ocu_show = $value;
		my $ocu = $value . ".001";
		$anz_total = $anz_total . ".001";
		my $percent_ocu;
		if ( $ocu eq "0.001" ) {
			$percent_ocu = "0";
		} else {
			$percent_ocu=100*$ocu/$anz_total;

			$percent_ocu =~ /^(\d+\.\d?).*/;
			$percent_ocu = $1;
		}

		my $form_name = "document.forms.list_host" . $j . ".submit()";
		$stylename="show_detail";
		if ( $color_helper eq "0" ) {
			$color="#f2f2f2";
			$color_helper="1";
		} else {
			$color="white";
			$color_helper="0";
		}

		if ( $stat_type eq "percent_range_bigger" ) {
			if ( $percent_ocu >= $percent_usage ) {
				print "<tr bgcolor=\"$color\" class=\"$stylename\" onClick=\"$form_name\" style=\"cursor:pointer;\"><td><b>$percent_ocu%</b> ($ocu_show/$anz_total_show)</td><td>&nbsp;&nbsp;&nbsp;$red_ip</td><td>&nbsp;&nbsp;&nbsp;$start_ip-$end_ip</td><td>&nbsp;&nbsp;&nbsp;$comentario</td><td>&nbsp;&nbsp;&nbsp;$range_type</td><td><form method=\"POST\" name=\"list_host$j\" action=\"$server_proto://$base_uri/ip_show.cgi\"><input name=\"red_num\" type=\"hidden\" value=\"$red_num\"><input name=\"client_id\" type=\"hidden\" value=\"$client_id\"></form></td></tr>";
			$found = "1";
			}
		} elsif (  $stat_type eq "percent_range_smaller" ) {
			if ( $percent_ocu < $percent_usage ) {
				print "<tr bgcolor=\"$color\" class=\"$stylename\" onClick=\"$form_name\" style=\"cursor:pointer;\"><td><b>$percent_ocu%</b> ($ocu_show/$anz_total_show)</td><td>&nbsp;&nbsp;&nbsp;$red_ip</td><td>&nbsp;&nbsp;&nbsp;$start_ip-$end_ip</td><td>&nbsp;&nbsp;&nbsp;$comentario</td><td>&nbsp;&nbsp;&nbsp;$range_type</td><td><form method=\"POST\" name=\"list_host$j\" action=\"$server_proto://$base_uri/ip_show.cgi\"><input name=\"red_num\" type=\"hidden\" value=\"$red_num\"><input name=\"client_id\" type=\"hidden\" value=\"$client_id\"></form></td></tr>";
			$found = "1";
			}
		}
		$j++;
	}
	print "</table>\n";
	if ( $found != "1" ) {
		print "<p class=\"NotifyText\">$$lang_vars{no_resultado_message}</p><br>\n";
		print "<p><FORM><INPUT TYPE=\"BUTTON\" VALUE=\"$$lang_vars{atras_message}\" ONCLICK=\"history.go(-1)\" class=\"error_back_link\"></FORM>\n";
		$gip->print_end("$client_id");
	}
}

$gip->print_end("$client_id");
