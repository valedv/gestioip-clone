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
use POSIX qw(strftime);
use lib './modules';
use GestioIP;
use Net::IP;
use Net::IP qw(:PROC);


my $daten=<STDIN>;
my $gip = GestioIP -> new();
my %daten=$gip->preparer("$daten");

my $base_uri=$gip->get_base_uri();
my $cgi_dir=$gip->get_cgi_dir();

my $lang = $daten{'lang'} || "";
my ($lang_vars,$vars_file)=$gip->get_lang("","$lang");
my $server_proto=$gip->get_server_proto();
my $client_id = $daten{'client_id'} || $gip->get_first_client_id();

my $back_button="<p><br><p><FORM><INPUT TYPE=\"BUTTON\" VALUE=\"back\" ONCLICK=\"history.go(-1)\" class=\"error_back_link\"></FORM>";

if ( ! $daten{'hostname'} && ! $daten{'host_descr'} && ! $daten{'comentario'} && ! $daten{'ip'} && ! $daten{'loc'} && ! $daten{'cat'} && ! $daten{'int_admin'} ) {
        $gip->print_init("search ip","$$lang_vars{busqueda_host_message}","$$lang_vars{no_search_string_message} $back_button","$vars_file","$client_id");
        $gip->print_end("$client_id");
        exit 1;
}

my $client_independent=$daten{client_independent} || "n";

no strict 'refs';
my @search;
foreach my $loc (keys %daten) {
	my $dat = $daten{$loc};
	if ( ! $dat ) { next; }
	if ( $loc eq "client_id" ) { next; }
	if ( $loc eq "client_independent" ) { next; }
	if ( $dat !~ /../ && $loc ne "int_admin" ) {
                $gip->print_init("search ip","$$lang_vars{busqueda_host_message}","$$lang_vars{dos_signos_message}","$vars_file","$client_id");
                $gip->print_end("$client_id");
                exit 1;
	}
	if ( $loc =~ /hostname/ || $dat =~ /$$lang_vars{buscar_message}/ || $loc =~ /search_index/ ) {
		next;
	}
	$dat = "$loc:X-X:$dat";
	push @search, $dat;
}

$gip->CheckInput("$client_id",\%daten,"$$lang_vars{mal_signo_error_message}","$$lang_vars{resultado_busqueda_message}","$vars_file");


my $hostname=$daten{'hostname'};
my $cat=$daten{'cat'} || "-1";
my $host_descr=$daten{'host_descr'};
my $comentario=$daten{'comentario'};
my $ip=$daten{'ip'};
my $loc=$daten{'loc'} || "-1";
my $int_admin=$daten{'int_admin'};
my $hostname_search;
my $BM;
my $int_admin_on = "";
my $search_index=$daten{'search_index'} || "false";
my $hostname_exact=$daten{'hostname_exact'} || "off";

if ( $hostname ) {
	$hostname =~ s/^\s*//;
	$hostname =~ s/\s*$//;
	# no search for "-ignore_string" only 
	if ( $search_index eq "true" && $hostname !~ /^-\S+$/ ) {
		my @hostnames;
		while ( 1 == 1 ) {
			if ( $hostname =~ /".+"/ ) {
				$hostname =~ s/"(.+?)"//;
				my $exact_hostname_string = $1 if $1;
				push (@hostnames,$exact_hostname_string) if $1;
			} else {
				$hostname =~ s/"//sg;
				last;
			}
		}
		my @mas_hostnames = split(" ",$hostname);
		@hostnames = (@hostnames, @mas_hostnames);

		my ( $ip_search, $ignore_search, $ip_cc_search, $cc_ignore_search);
		foreach ( @hostnames ) {
			if ( $_ !~ /^-/ && $_ !~ /^\+/ ) {

				$ip_cc_search = "";
				$ip_cc_search = " OR (h.id IN (SELECT host_id FROM custom_host_column_entries WHERE entry LIKE \"%$_%\"))";
 
				if ( ! $ip_search ) {
					$ip_search = "( INET_NTOA(h.ip) LIKE \"%$_%\" OR h.hostname LIKE \"%$_%\" OR h.host_descr LIKE \"%$_%\" OR h.comentario LIKE \"%$_%\" OR l.loc LIKE \"%$_%\" OR c.cat LIKE \"%$_%\" $ip_cc_search)";
				} else {
					$ip_search =  $ip_search . " AND ( INET_NTOA(h.ip) LIKE \"%$_%\" OR h.hostname LIKE \"%$_%\" OR h.host_descr LIKE \"%$_%\" OR h.comentario LIKE \"%$_%\" OR l.loc LIKE \"%$_%\" OR c.cat LIKE \"%$_%\" $ip_cc_search)";
				}
			} elsif ( $_ =~ /^-/ ) {
				$_ =~ s/^-//;

				$cc_ignore_search = "";
				$cc_ignore_search = " AND (h.id NOT IN (SELECT host_id FROM custom_host_column_entries WHERE entry REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" ))";
				if ( ! $ignore_search ) {
					$ignore_search = "( INET_NTOA(h.ip) NOT REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" AND h.hostname NOT REGEXP \"\[\[:<:]]$_\[\[:>:\]\]\" AND h.host_descr NOT REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" AND h.comentario NOT REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" AND l.loc NOT REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" AND c.cat NOT REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" $cc_ignore_search)";
				} else {
					$ignore_search = $ignore_search . " AND ( INET_NTOA(h.ip) NOT REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" AND h.hostname NOT REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" AND h.host_descr NOT REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" AND h.comentario NOT REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" AND l.loc NOT REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" AND c.cat NOT REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" $cc_ignore_search)";
				}
			 #$_ begins with "+"
			} elsif ( $_ =~ /^\+/ ) {
				$_ =~ s/^\+//;
				$ip_cc_search= "";
				$ip_cc_search= " OR (h.id IN (SELECT host_id FROM custom_host_column_entries WHERE entry = \"$_\" ))";
				if ( ! $ip_search ) {
					$ip_search = "( INET_NTOA(h.ip)=\"$_\" OR h.hostname=\"$_\" OR h.host_descr=\"$_\" OR h.comentario=\"$_\" OR l.loc=\"$_\" OR c.cat=\"$_\" $ip_cc_search)";
				} else {
					$ip_search = $ip_search . " AND ( INET_NTOA(h.ip)=\"$_\" OR h.hostname=\"$_\" OR h.host_descr=\"$_\" OR h.comentario=\"$_\" OR l.loc=\"$_\" OR c.cat=\"$_\" $ip_cc_search)";
				}
			} else {
				$ip_cc_search= "";
				$ip_cc_search= " OR (h.id IN (SELECT host_id FROM custom_host_column_entries WHERE entry REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" ))";
				if ( ! $ignore_search ) {
					$ignore_search = "( INET_NTOA(h.ip) REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" OR h.hostname REGEXP \"\[\[:<:]]$_\[\[:>:\]\]\" OR h.host_descr REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" OR h.comentario REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" AND l.loc NOT REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" AND c.cat NOT REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" $ip_cc_search)";
				} else {
					$ignore_search = $ignore_search . " AND ( INET_NTOA(h.ip) REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" OR h.hostname REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" OR h.host_descr REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" OR h.comentario REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" AND l.loc NOT REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" AND c.cat NOT REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" $ip_cc_search)";
				}
			}
		}

		$ignore_search = "( ". $ignore_search . " )" if $ignore_search;
		if ( $ip_search && $ignore_search ) {
			$hostname_search = " $ip_search AND $ignore_search ";
		} elsif ( $ip_search && ! $ignore_search ) {
			$hostname_search = " $ip_search ";
		} else {
			$hostname_search=" $ignore_search ";
		}
	} elsif ( $search_index eq "true" && $hostname =~ /^-\S+$/ ) {
			print "<p class=\"NotifyText\">$$lang_vars{exclude_string_only_message}</p><br>\n";
			$gip->print_end("$client_id");
			exit 1;
        } else {
		if ( $hostname_exact eq "on" ) {
			$hostname_search="hostname LIKE \"$hostname\"";
		} else {
			$hostname_search="hostname LIKE \"%$hostname%\"";
		}
	}
} else {
	$hostname_search="";
}

if ( $hostname_search ) {
	push @search, $hostname_search;
}

my ($host_hash_ref,$host_sort_helper_array_ref)=$gip->search_db_hash("$client_id",\@search,"$client_independent") if $search[0];

my $anz_values_hosts += keys %$host_hash_ref;
my $knownhosts="all";
my $start_entry_hosts="0";
my $entries_per_page_hosts="512";
my $pages_links="NO_LINKS";
my $host_order_by = "SEARCH";
my $red_num = "";
my $red_loc = "";
my $redbroad_int = "1";
my $first_ip_int = "";
my $last_ip_int = "";


if ( $anz_values_hosts < "1" ) {
	print "<p class=\"NotifyText\">$$lang_vars{no_resultado_message}</p><br>\n";
	$gip->print_end("$client_id","$vars_file","go_to_top");
} elsif ( $anz_values_hosts > 500 ) {
	print "<p class=\"NotifyText\">$$lang_vars{max_search_result_host_superado_message}</p><br>\n";
	$gip->print_end("$client_id","$vars_file","go_to_top");
}

print "<p>\n";

$gip->PrintIpTab("$client_id",$host_hash_ref,"$first_ip_int","$last_ip_int","res/ip_modip_form.cgi","$knownhosts","$$lang_vars{modificar_message}","$red_num","$red_loc","$vars_file","$anz_values_hosts","$start_entry_hosts","$entries_per_page_hosts","$host_order_by",$host_sort_helper_array_ref,"$client_independent");

$gip->print_end("$client_id","$vars_file","go_to_top");

