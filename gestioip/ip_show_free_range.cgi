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
my ($lang_vars,$vars_file,$entries_per_page);
if ( $daten{'entries_per_page'} ) {
        $daten{'entries_per_page'} = "500" if $daten{'entries_per_page'} !~ /^\d{1,3}$/;
        ($lang_vars,$vars_file,$entries_per_page)=$gip->get_lang("$daten{'entries_per_page'}","$lang");
} else {
        ($lang_vars,$vars_file,$entries_per_page)=$gip->get_lang("","$lang");
}

my $client_id = $daten{'client_id'} || $gip->get_first_client_id();

my @global_config = $gip->get_global_config("$client_id");
my $global_ip_version=$global_config[0]->[5] || "v4";
my $ip_version_ele="";
if ( $global_ip_version ne "yes" ) {
$ip_version_ele = $daten{'ip_version_ele'} || "";
if ( $ip_version_ele ) {
	$ip_version_ele = $gip->set_ip_version_ele("$ip_version_ele");
	} else {
		$ip_version_ele = $gip->get_ip_version_ele();
	}
} else {
	$ip_version_ele = "v4";
}

my $rootnet=$daten{'rootnet'} || "n";
my $rootred_num=$daten{'red_num'} || "0";
my $ip_version=$daten{'ip_version'} || "";

my ( $rootnet_ip, $rootnet_BM);
my @values_red;
if ( $rootnet eq "y" ) {
	@values_red = $gip->get_red("$client_id","$rootred_num");
	$rootnet_ip = $values_red[0]->[0];
	$rootnet_BM = $values_red[0]->[1];
	$gip->CheckInput("$client_id",\%daten,"$$lang_vars{mal_signo_error_message}","$$lang_vars{rootnet_message} $rootnet_ip/$rootnet_BM","$vars_file");
} else {
	$gip->CheckInput("$client_id",\%daten,"$$lang_vars{mal_signo_error_message}","$$lang_vars{show_free_range_message}","$vars_file");
}


my $tipo_ele = $daten{'tipo_ele'} || "NULL";
my $loc_ele = $daten{'loc_ele'} || "NULL";
my $start_entry=$daten{'start_entry'} || '0';
my $order_by=$daten{'order_by'} || 'red_auf';
$gip->print_error("$client_id",$$lang_vars{formato_malo_message}) if $start_entry !~ /^\d{1,4}$/;


my $tipo_ele_id=$gip->get_cat_net_id("$client_id","$tipo_ele") || "-1";
my $loc_ele_id=$gip->get_loc_id("$client_id","$loc_ele") || "-1";
my @ip;
my ( $anz_values_redes, $pages_links);
if ( $rootnet eq "n" ) {
	$anz_values_redes = $gip->count_red_entries_all("$client_id","$tipo_ele","$loc_ele","","$ip_version_ele");
	$pages_links=$gip->get_pages_links_red("$client_id","$start_entry","$anz_values_redes","$entries_per_page","$tipo_ele","$loc_ele","$order_by");
	@ip=$gip->get_redes("$client_id","$tipo_ele_id","$loc_ele_id","$start_entry","$entries_per_page","$order_by","$ip_version_ele");
} else {
	my $overlap_check_red_num = $values_red[0]->[8] || "0";
	my @overlap_redes=$gip->get_redes("$client_id","$tipo_ele_id","$loc_ele_id","$start_entry","$entries_per_page","$order_by","$ip_version_ele");
	my @overlap_found = $gip->find_overlap_redes("$client_id","$rootnet_ip","$rootnet_BM",\@overlap_redes,"$ip_version_ele","$vars_file","$rootnet","$overlap_check_red_num" );
	$anz_values_redes=scalar(@overlap_found);
	$pages_links=$gip->get_pages_links_red("$client_id","$start_entry","$anz_values_redes","$entries_per_page","$tipo_ele","$loc_ele","$order_by");
#	@ip=@overlap_found;
	my @overlap_rootnets = ();
	my $i="0";
	foreach (@overlap_found) {
		push (@overlap_rootnets,$overlap_found[$i]) if $overlap_found[$i]->[10] == "1";
		$i++;
	}
	my @overlap_found_new = ();
	$i="0";
	if ( $overlap_rootnets[0]->[0] ) {
		## eleminate networks from @overlap_found with are subnets of rootnets of rootnets
		foreach (@overlap_rootnets) {
			my $rootnet_ip_sub=$overlap_rootnets[$i]->[0];
			my $rootnet_BM_sub=$overlap_rootnets[$i]->[1];
			my $overlap_check_red_num_sub=$overlap_rootnets[$i]->[3];
			my @overlap_found_sub=$gip->find_overlap_redes("$client_id","$rootnet_ip_sub","$rootnet_BM_sub",\@overlap_redes,"$ip_version_ele","$vars_file","1","$overlap_check_red_num_sub" );
			# eleminate elements of @overlap_found_sub from @overlap_found, @new contains the elements which are in @overlap_found
			# but not in @overlap_found_sub
			
			my %seen = ();
			my @new = ();
			@seen{@overlap_found_sub} = ();
			foreach my $item (@overlap_found) {
				push(@new, $item) unless exists $seen{$item};
			}
			@overlap_found = @new;
			$i++;
		}
		@ip=@overlap_found;
	} else {
		@ip=@overlap_found;
	}
}
my $ip=$gip->prepare_redes_array("$client_id",\@ip,"$order_by","$start_entry","$entries_per_page","$ip_version_ele");

$gip->PrintRedTabHead("$client_id","$vars_file","$start_entry","$entries_per_page","$pages_links","$tipo_ele","$loc_ele","$ip_version_ele");
if ( @ip ) {
	$gip->PrintRedTab("$client_id",$ip,"$vars_file","simple","$start_entry","$tipo_ele","$loc_ele","$order_by","","","$ip_version_ele");

} else {
	if ( $rootnet eq "n" ) {
		print "<p class=\"NotifyText\">$$lang_vars{no_resultado_message}</p><br>\n";
	} else {
		print "<p class=\"NotifyText\">$$lang_vars{rootnet_has_no_subnets_message}</p><br>\n";
### TEST
#		my $rootnet_int = $gip->ip_to_int("$rootnet","$ip_version");
#		my $base_uri = $gip->get_base_uri();
#		my $server_proto=$gip->get_server_proto();
#		print "<p class=\"input_link_w\" onClick=\"create_net.submit()\" style=\"cursor:pointer;\" title=\"$$lang_vars{create_net_freeranges_message}\"><form method=\"POST\" name=\"create_net\" action=\"$server_proto://$base_uri/res/ip_insertred_form.cgi\"> NEW<input name=\"ip\" type=\"hidden\" value=\"$rootnet_int/0\"><input name=\"client_id\" type=\"hidden\" value=\"$client_id\"><input name=\"ip_version\" type=\"hidden\" value=\"$ip_version\"></form></p>\n";
	}
}

$gip->print_end("$client_id","$vars_file");
