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
my %daten=$gip->preparer($daten);

my $lang = $daten{'lang'} || "";
my ($lang_vars,$vars_file)=$gip->get_lang("","$lang");

my $client_id = $daten{'client_id'} || $gip->get_first_client_id();
if ( $client_id !~ /^\d{1,4}$/ ) {
        $gip->CheckInput("$client_id",\%daten,"$$lang_vars{mal_signo_error_message}","$$lang_vars{busqueda_red_message}","$vars_file");
	$client_id=$gip->get_first_client_id();
        $gip->print_error("$client_id","$$lang_vars{client_id_invalid_message}","");
}

my $modred=$daten{modred} || "";
my $client_independent=$daten{client_independent} || "n";

my $back_button="<p><br><p><FORM><INPUT TYPE=\"BUTTON\" VALUE=\"back\" ONCLICK=\"history.go(-1)\" class=\"error_back_link\"></FORM>";


no strict 'refs';
my @search;
my @cc_search;
my @cc_ignore_search;
foreach my $loc (keys %daten) {
        my $dat = $daten{$loc};
        if ( ! $dat ) { next; }
        if ( $loc eq "client_id" ) { next; }
        if ( $loc eq "client_independent" ) { next; }
        if ( $dat !~ /../ && $loc ne "vigilada" && $modred ne "y") {
                $gip->print_init("search ip","$$lang_vars{busqueda_red_message}","$$lang_vars{dos_signos_message}","$vars_file","$client_id");
                $gip->print_end("$client_id");
                exit 1;
        }
        if ( $dat =~ /$$lang_vars{buscar_message}/ || $loc =~ /search_index/ || $loc =~ /modred/ || $loc =~ /red_search/) {
                next;
        }
        $dat = "$loc:X-X:$dat";
        push @search, $dat;
}
use strict 'refs';

if ( ! $daten{'red_search'} && ! $daten{'red'} && ! $daten{'descr'} && ! $daten{'loc'} && ! $daten{'vigilada'} && ! $daten{'cat_red'} && ! $daten{'comentario'} ) {
        $gip->print_init("search ip","$$lang_vars{busqueda_red_message}","$$lang_vars{no_search_string_message} $back_button","$vars_file","$client_id");
        $gip->print_end("$client_id");
        exit 1;
}

$gip->CheckInput("$client_id",\%daten,"$$lang_vars{mal_signo_error_message}","$$lang_vars{resultado_busqueda_message}","$vars_file");


my $search_index=$daten{'search_index'} || "false";
my $mas_red_search;
my $mas_red_cc_search;
my $mas_red_cc_ignore_search;
my @red_search;
my @ignore_search;
my @red_cc_search;
my $red_search;
my $ip_cc_search = "";
my $cc_ignore_search = "";
my $ip_search = "";
my $ignore_search = "";

if ( $daten{'red_search'} ) {
	$red_search = $daten{'red_search'};
	$red_search =~ s/^\s*//;
	$red_search =~ s/\s*$//;
}

if ( $search_index eq "true" ) {
	if ( $red_search =~ /^-\S+$/ ) {
		print "<p class=\"NotifyText\">$$lang_vars{exclude_string_only_message}</p><br>\n";
		$gip->print_end("$client_id");
		exit 1;
	}
	my @red_search_array; 
	while ( 1 == 1 ) {
		if ( $red_search =~ /".+"/ ) {
			$red_search =~ s/"(.+?)"//;
			my $exact_red_search_string = $1 if $1;
			push (@red_search,$exact_red_search_string) if $1;
		} else {
			$red_search =~ s/"//sg;
			last;
		}
	}
	my @mas_red_search = split(" ",$red_search);
	@red_search = (@red_search, @mas_red_search);

	foreach ( @red_search ) {
		if ( $_ !~ /^-/ && $_ !~ /^\+/ ) {

			$ip_cc_search = "";
			$ip_cc_search = " OR (n.red_num IN (SELECT net_id FROM custom_net_column_entries WHERE entry LIKE \"%$_%\"))";
			if ( ! $ip_search ) {
				$ip_search = "( red LIKE \"%$_%\" OR descr LIKE \"%$_%\" OR comentario LIKE \"%$_%\" OR l.loc LIKE \"%$_%\" OR c.cat LIKE \"%$_%\" $ip_cc_search) ";
			} else {
				$ip_search =  $ip_search . " AND ( red LIKE \"%$_%\" OR descr LIKE \"%$_%\" OR comentario LIKE \"%$_%\" OR l.loc LIKE \"%$_%\" OR c.cat LIKE \"%$_%\" $ip_cc_search)";
			}

		} elsif ( $_ =~ /^-/ ) {
			$_ =~ s/^-//;
			$cc_ignore_search = "";
			$cc_ignore_search = " AND (n.red_num NOT IN (SELECT net_id FROM custom_net_column_entries WHERE entry REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" ))";
			if ( ! $ignore_search ) {
				$ignore_search = "( red NOT REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" AND descr NOT REGEXP \"\[\[:<:]]$_\[\[:>:\]\]\" AND comentario NOT REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" AND l.loc NOT REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" AND c.cat NOT REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" $cc_ignore_search )";
			} else {
				$ignore_search = $ignore_search . " AND ( red NOT REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" AND descr NOT REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" AND comentario NOT REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" AND l.loc NOT REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" AND c.cat NOT REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" )";
			}

		} elsif ( $_ =~ /^\+/ ) {
			$_ =~ s/^\+//;
			$ip_cc_search= "";
			$ip_cc_search= " OR (n.red_num IN (SELECT net_id FROM custom_net_column_entries WHERE entry = \"$_\" ))";
			if ( ! $ip_search ) {
				$ip_search = "( red = \"$_\" OR descr = \"$_\" OR comentario = \"$_\" OR l.loc = \"$_\" OR c.cat = \"$_\" $ip_cc_search)";
			} else {
				$ip_search = $ip_search . " AND ( red = \"$_\" OR descr = \"$_\" OR comentario = \"$_\" OR l.loc = \"$_\" OR c.cat = \"$_\" $ip_cc_search)";
			}
		} else {
			$ip_cc_search= "";
			$ip_cc_search= " OR (n.red_num IN (SELECT net_id FROM custom_net_column_entries WHERE entry REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" ))";
			if ( ! $ip_search ) {
				$ip_search = "( red REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" OR descr REGEXP \"\[\[:<:]]$_\[\[:>:\]\]\" OR comentario REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" OR l.loc REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" OR c.cat REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" $ip_cc_search)";
			} else {
				$ip_search = $ip_search . " AND ( red REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" OR descr REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" OR comentario REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" OR l.loc REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" OR c.cat REGEXP \"\[\[:<:\]\]$_\[\[:>:\]\]\" $ip_cc_search)";
			}
		}

	}
	$ignore_search = "( ". $ignore_search . " )" if $ignore_search;
	$cc_ignore_search = "( ". $cc_ignore_search . " )" if $cc_ignore_search;

}

if ( $ip_search ) {
	push @search, $ip_search;
}
if ( $ignore_search ) {
	push @ignore_search, $ignore_search;
}


my @values_red=$gip->search_db_red("$client_id",\@search,\@ignore_search,"$search_index","$client_independent") if $search[0] || $ignore_search[0];

my $values_red_num = @values_red || "0";
my $colorcomment;

if ( ! $values_red[0] ) {
	print "<p class=\"NotifyText\">$$lang_vars{no_resultado_message}</p><br>\n";
	$colorcomment="nocomment";
} elsif ( $values_red_num > 300 ) {
        print "<p class=\"NotifyText\">$$lang_vars{max_search_result_net_superado_message}</p><br>\n";
} else {
#	$gip->PrintRedTabHead("$client_id","$vars_file");
	print "<p>\n";
	if ( $modred eq "y" ) {
		$gip->PrintRedTab("$client_id",\@values_red,"$vars_file","extended");
	} else { 
		$gip->PrintRedTab("$client_id",\@values_red,"$vars_file","simple","","","","","$client_independent");
	}
	$colorcomment="nocomment";
}

$gip->print_end("$client_id","$vars_file");
